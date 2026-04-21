"""browser_history.py — Scan browser history databases for visited URLs.

Supports:
  - Google Chrome / Chromium (including snap installs)
  - Mozilla Firefox         (including snap installs)
  - Microsoft Edge
  - Brave                   (including snap install)
  - Google Chrome (snap)

Changes in this version
-----------------------
1. WAL/SHM copy — Chrome and Firefox both use SQLite WAL mode.  The previous
   code copied only the main DB file, missing recent transactions still in the
   write-ahead log.  Now History-wal / History-shm (and places.sqlite-wal /
   places.sqlite-shm) are also copied when present.

2. Lookback window — a BROWSER_HISTORY_LOOKBACK_SECONDS constant (default 300 s
   = 5 minutes) is subtracted from agent_start_time so URLs visited just before
   the student clicked Start are not silently dropped.

3. Snap profile paths — added current-generation snap paths for Chromium,
   Firefox, Brave, and the snap-packaged Google Chrome.

4. Poll interval in dispatcher — reduced from 30 s to 15 s (applied in
   dispatcher.py, documented here for clarity).

Performance notes
-----------------
* Each browser DB is copied to a unique temp path so parallel scans never
  clobber each other's temp file.
* All blocking I/O is isolated inside plain functions that callers must run in
  a thread executor — get_new_history() is a regular (non-async) function by
  design so it can be safely passed to loop.run_in_executor().
* scan_browser_history short-circuits if no browser DB files exist, avoiding
  repeated glob work every poll cycle.
"""

import logging
import os
import shutil
import sqlite3
import time
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("lab_guardian.monitor.browser_history")

# ---------------------------------------------------------------------------
# Lookback window
# ---------------------------------------------------------------------------

# Include history from this many seconds BEFORE the agent started.
# This handles the common case of a student who opened the browser before
# clicking Start, and the Chrome write-back lag (typically 5–60 s).
BROWSER_HISTORY_LOOKBACK_SECONDS: float = 300.0  # 5 minutes


# ---------------------------------------------------------------------------
# Browser path definitions
# ---------------------------------------------------------------------------

BROWSER_PATHS = {
    'chrome': {
        'linux': [
            '~/.config/google-chrome/Default/History',
        ],
        'windows': [
            '~/AppData/Local/Google/Chrome/User Data/Default/History',
        ],
        'name': 'Google Chrome',
    },
    # Snap-packaged Google Chrome (separate entry so _build_db_path_list can
    # include it without duplicating the native chrome paths)
    'chrome_snap': {
        'linux': [
            '~/snap/google-chrome/common/google-chrome/Default/History',
            '~/snap/google-chrome/current/google-chrome/Default/History',
        ],
        'windows': [],
        'name': 'Google Chrome (Snap)',
    },
    'chromium': {
        'linux': [
            '~/.config/chromium/Default/History',
            # Snap — common (older Ubuntu)
            '~/snap/chromium/common/chromium/Default/History',
            '~/snap/chromium/common/.config/chromium/Default/History',
            # Snap — current (Ubuntu 22.04+)
            '~/snap/chromium/current/.config/chromium/Default/History',
        ],
        'windows': [
            '~/AppData/Local/Chromium/User Data/Default/History',
        ],
        'name': 'Chromium',
    },
    'brave': {
        'linux': [
            '~/.config/BraveSoftware/Brave-Browser/Default/History',
            '~/snap/brave/common/.config/BraveSoftware/Brave-Browser/Default/History',
            # Snap — current slot
            '~/snap/brave/current/.config/BraveSoftware/Brave-Browser/Default/History',
        ],
        'windows': [
            '~/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/History',
        ],
        'name': 'Brave',
    },
    'edge': {
        'linux': [
            '~/.config/microsoft-edge/Default/History',
        ],
        'windows': [
            '~/AppData/Local/Microsoft/Edge/User Data/Default/History',
        ],
        'name': 'Microsoft Edge',
    },
    'firefox': {
        'linux': [
            '~/.mozilla/firefox/*/places.sqlite',
            # Snap — common
            '~/snap/firefox/common/.mozilla/firefox/*/places.sqlite',
            # Snap — current slot (Ubuntu 22.04+)
            '~/snap/firefox/current/.mozilla/firefox/*/places.sqlite',
        ],
        'windows': [
            '~/AppData/Roaming/Mozilla/Firefox/Profiles/*/places.sqlite',
        ],
        'name': 'Mozilla Firefox',
    },
}


def _get_browser_db_path(browser_key: str) -> List[str]:
    """Return resolved DB paths for a browser, with glob expansion."""
    import platform

    browser_info = BROWSER_PATHS.get(browser_key, {})
    os_name = platform.system().lower()
    path_templates = browser_info.get('windows' if 'windows' in os_name else 'linux', [])

    results: List[str] = []
    for template in path_templates:
        path = os.path.expanduser(template)
        if '*' in path:
            results.extend(p for p in glob(path) if os.path.isfile(p))
        elif os.path.isfile(path):
            results.append(path)
    return results


# ---------------------------------------------------------------------------
# WAL / SHM helper
# ---------------------------------------------------------------------------

def _copy_with_wal(src_db: str, dst_db: str) -> None:
    """Copy *src_db* to *dst_db*, also copying -wal and -shm side-files.

    SQLite WAL mode keeps recent (uncommitted) transactions in a separate
    -wal file.  If we only copy the main DB, queries will miss data that the
    browser has written but not yet checkpointed.

    Failures when copying the WAL/SHM files are silently ignored — the main
    DB copy still proceeds and results will simply be slightly stale.
    """
    shutil.copy2(src_db, dst_db)
    for suffix in ("-wal", "-shm"):
        src_side = src_db + suffix
        if os.path.isfile(src_side):
            try:
                shutil.copy2(src_side, dst_db + suffix)
            except OSError as exc:
                log.debug("Could not copy %s: %s", src_side, exc)


# ---------------------------------------------------------------------------
# Chrome / Chromium / Brave / Edge reader
# ---------------------------------------------------------------------------

_CHROME_EPOCH_OFFSET = 11644473600000000  # µs between 1601-01-01 and 1970-01-01


def _read_chrome_history(db_path: str, since_timestamp: Optional[float], browser_name: str = "Chrome") -> List[Dict]:
    """Read a Chrome-family History SQLite file.

    Copies the file (plus WAL/SHM) to a unique temp path first to avoid
    locking the live DB and to capture uncommitted WAL transactions.
    """
    urls: List[Dict] = []
    pid = os.getpid()
    temp_db = f"/tmp/lg_chrome_{pid}_{abs(hash(db_path)) % 100000}.db"

    try:
        _copy_with_wal(db_path, temp_db)

        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True, timeout=5)
        conn.row_factory = None  # raw tuples are faster

        if since_timestamp is not None:
            chrome_ts = int(since_timestamp * 1_000_000) + _CHROME_EPOCH_OFFSET
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_time "
                "FROM urls WHERE last_visit_time > ? "
                "ORDER BY last_visit_time DESC LIMIT 500",
                (chrome_ts,),
            )
        else:
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_time "
                "FROM urls ORDER BY last_visit_time DESC LIMIT 500"
            )

        rows = cursor.fetchall()
        conn.close()

        for url, title, visit_count, chrome_time in rows:
            unix_ts = (
                (chrome_time - _CHROME_EPOCH_OFFSET) / 1_000_000.0
                if chrome_time and chrome_time > 0
                else 0
            )
            urls.append({
                'url': url,
                'title': title or '',
                'visit_count': visit_count or 1,
                'last_visited': unix_ts,
                'browser': browser_name,
            })

        log.debug("%s %s: %d rows", browser_name, db_path, len(rows))

    except Exception as exc:
        log.error("Error reading %s history from %s: %s", browser_name, db_path, exc)
    finally:
        # Clean up all temp files
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(temp_db + suffix)
            except OSError:
                pass

    return urls


# ---------------------------------------------------------------------------
# Firefox reader
# ---------------------------------------------------------------------------

def _read_firefox_history(db_path: str, since_timestamp: Optional[float]) -> List[Dict]:
    """Read a Firefox places.sqlite file.

    Also copies WAL/SHM files to capture recent uncommitted writes.
    """
    urls: List[Dict] = []
    pid = os.getpid()
    temp_db = f"/tmp/lg_firefox_{pid}_{abs(hash(db_path)) % 100000}.db"

    try:
        _copy_with_wal(db_path, temp_db)

        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True, timeout=5)
        conn.row_factory = None

        if since_timestamp is not None:
            # Firefox stores microseconds since Unix epoch
            firefox_ts = int(since_timestamp * 1_000_000)
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_date "
                "FROM moz_places "
                "WHERE visit_count > 0 AND last_visit_date > ? "
                "ORDER BY last_visit_date DESC LIMIT 500",
                (firefox_ts,),
            )
        else:
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_date "
                "FROM moz_places WHERE visit_count > 0 "
                "ORDER BY last_visit_date DESC LIMIT 500"
            )

        rows = cursor.fetchall()
        conn.close()

        for url, title, visit_count, moz_time in rows:
            unix_ts = moz_time / 1_000_000.0 if moz_time and moz_time > 0 else 0
            urls.append({
                'url': url,
                'title': title or '',
                'visit_count': visit_count or 1,
                'last_visited': unix_ts,
                'browser': 'Firefox',
            })

        log.debug("Firefox %s: %d rows", db_path, len(rows))

    except Exception as exc:
        log.error("Error reading Firefox history from %s: %s", db_path, exc)
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(temp_db + suffix)
            except OSError:
                pass

    return urls


# ---------------------------------------------------------------------------
# Public scan API
# ---------------------------------------------------------------------------

_known_db_paths: Optional[List[tuple]] = None
_known_db_paths_built_at: float = 0.0
_DB_PATH_CACHE_TTL = 60.0  # re-scan filesystem for new browsers every 60 s


def _build_db_path_list() -> List[tuple]:
    """Return list of (browser_key, db_path, is_firefox, browser_name) for all found DBs."""
    found = []
    # Chrome-family browsers (non-Firefox)
    for bkey in ('chrome', 'chrome_snap', 'chromium', 'brave', 'edge'):
        browser_name = BROWSER_PATHS.get(bkey, {}).get('name', bkey)
        for p in _get_browser_db_path(bkey):
            found.append((bkey, p, False, browser_name))
    # Firefox
    for p in _get_browser_db_path('firefox'):
        found.append(('firefox', p, True, 'Firefox'))
    log.debug("Browser DB discovery: %d database(s) found", len(found))
    return found


def scan_browser_history(since_timestamp: Optional[float] = None) -> List[Dict]:
    """Scan all available browser histories.

    This is a blocking function.  Callers running inside an async event loop
    must wrap it in ``loop.run_in_executor(None, scan_browser_history, ts)``.

    Args:
        since_timestamp: Only return URLs visited after this Unix timestamp.
                         Pass None to return all history.

    Returns:
        List of dicts: url, title, visit_count, last_visited (Unix float), browser.
    """
    global _known_db_paths, _known_db_paths_built_at

    now = time.time()
    if _known_db_paths is None or (now - _known_db_paths_built_at) > _DB_PATH_CACHE_TTL:
        _known_db_paths = _build_db_path_list()
        _known_db_paths_built_at = now

    if not _known_db_paths:
        return []

    all_urls: List[Dict] = []
    for _bkey, db_path, is_firefox, browser_name in _known_db_paths:
        if not os.path.isfile(db_path):
            continue
        if is_firefox:
            all_urls.extend(_read_firefox_history(db_path, since_timestamp))
        else:
            all_urls.extend(_read_chrome_history(db_path, since_timestamp, browser_name))

    all_urls.sort(key=lambda x: x['last_visited'], reverse=True)
    log.debug("scan_browser_history: %d total URLs", len(all_urls))
    return all_urls


# ---------------------------------------------------------------------------
# Agent lifecycle helpers
# ---------------------------------------------------------------------------

_agent_start_time: float = 0.0
_last_scan_time: float = 0.0
_last_urls: List[Dict] = []


def initialize_agent_start_time() -> None:
    """Record the agent start time.  Call once when monitoring begins."""
    global _agent_start_time
    _agent_start_time = time.time()
    log.info("Browser history monitor start time: %s", time.ctime(_agent_start_time))


def get_new_history() -> List[Dict]:
    """Return URLs visited since (agent_start_time - BROWSER_HISTORY_LOOKBACK_SECONDS).

    Using a lookback window instead of the exact start time handles:
    - Chrome's write-back lag (DB can be 5–60 s behind actual activity)
    - Students who open a browser tab before clicking Start

    This is a **blocking** function.  The dispatcher must call it inside
    ``loop.run_in_executor`` so it does not block the event loop.
    """
    global _last_scan_time, _last_urls
    try:
        # Subtract the lookback window so recently-visited but not-yet-flushed
        # URLs are captured on subsequent scans.
        if _agent_start_time > 0:
            since_ts = _agent_start_time - BROWSER_HISTORY_LOOKBACK_SECONDS
        else:
            since_ts = None

        urls = scan_browser_history(since_timestamp=since_ts)
        _last_scan_time = time.time()
        _last_urls = urls
        return urls
    except Exception as exc:
        log.error("Error in get_new_history: %s", exc)
        return []