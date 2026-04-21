"""browser_history.py — Scan browser history databases for visited URLs.

Supports:
  - Google Chrome / Chromium
  - Mozilla Firefox
  - Microsoft Edge
  - Brave

Extracts full URLs with visit timestamps and visit counts.

Performance notes
-----------------
* Each browser DB is copied to a unique temp path so parallel scans
  never clobber each other's temp file.
* All blocking I/O (shutil.copy2, sqlite3 queries) is isolated inside
  plain functions that callers must run in a thread executor —
  ``get_new_history`` is a regular (non-async) function by design so it
  can be safely passed to ``loop.run_in_executor`` in the dispatcher.
* ``scan_browser_history`` short-circuits if no browser DB files exist,
  avoiding repeated glob work every poll cycle.
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
# Browser path definitions
# ---------------------------------------------------------------------------

BROWSER_PATHS = {
    'chrome': {
        'linux': ['~/.config/google-chrome/Default/History'],
        'windows': ['~/AppData/Local/Google/Chrome/User Data/Default/History'],
        'name': 'Google Chrome',
    },
    'chromium': {
        'linux': [
            '~/.config/chromium/Default/History',
            '~/snap/chromium/common/chromium/Default/History',
        ],
        'windows': ['~/AppData/Local/Chromium/User Data/Default/History'],
        'name': 'Chromium',
    },
    'brave': {
        'linux': [
            '~/.config/BraveSoftware/Brave-Browser/Default/History',
            '~/snap/brave/common/.config/BraveSoftware/Brave-Browser/Default/History',
        ],
        'windows': ['~/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/History'],
        'name': 'Brave',
    },
    'edge': {
        'linux': ['~/.config/microsoft-edge/Default/History'],
        'windows': ['~/AppData/Local/Microsoft/Edge/User Data/Default/History'],
        'name': 'Microsoft Edge',
    },
    'firefox': {
        'linux': [
            '~/.mozilla/firefox/*/places.sqlite',
            '~/snap/firefox/common/.mozilla/firefox/*/places.sqlite',
        ],
        'windows': ['~/AppData/Roaming/Mozilla/Firefox/Profiles/*/places.sqlite'],
        'name': 'Mozilla Firefox',
    },
}

# Cache resolved DB paths so glob is not re-run every poll cycle.
# Invalidated when mtime of parent directory changes.
_PATH_CACHE: Dict[str, List[str]] = {}
_PATH_CACHE_MTIME: Dict[str, float] = {}


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
# Chrome / Chromium / Brave / Edge reader
# ---------------------------------------------------------------------------

_CHROME_EPOCH_OFFSET = 11644473600000000  # microseconds between 1601-01-01 and 1970-01-01


def _read_chrome_history(db_path: str, since_timestamp: Optional[float]) -> List[Dict]:
    """Read a Chrome-family History SQLite file.

    Copies the file to a unique temp path first to avoid locking the live DB.
    """
    urls: List[Dict] = []
    pid = os.getpid()
    # Use id(db_path) to make the temp name unique per source file within
    # the same process, preventing concurrent scans from clobbering each other.
    temp_db = f"/tmp/lg_chrome_{pid}_{abs(hash(db_path)) % 100000}.db"

    try:
        shutil.copy2(db_path, temp_db)
        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True, timeout=5)
        conn.row_factory = None  # raw tuples are faster than Row objects

        if since_timestamp:
            chrome_ts = int(since_timestamp * 1_000_000) + _CHROME_EPOCH_OFFSET
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_time "
                "FROM urls WHERE last_visit_time > ? "
                "ORDER BY last_visit_time DESC LIMIT 200",
                (chrome_ts,),
            )
        else:
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_time "
                "FROM urls ORDER BY last_visit_time DESC LIMIT 200"
            )

        rows = cursor.fetchall()
        conn.close()

        for url, title, visit_count, chrome_time in rows:
            unix_ts = (chrome_time - _CHROME_EPOCH_OFFSET) / 1_000_000.0 if chrome_time and chrome_time > 0 else 0
            urls.append({
                'url': url,
                'title': title or '',
                'visit_count': visit_count or 1,
                'last_visited': unix_ts,
                'browser': 'Chrome',
            })

        log.debug("Chrome %s: %d rows", db_path, len(rows))

    except Exception as exc:
        log.error("Error reading Chrome history from %s: %s", db_path, exc)
    finally:
        try:
            os.remove(temp_db)
        except OSError:
            pass

    return urls


# ---------------------------------------------------------------------------
# Firefox reader
# ---------------------------------------------------------------------------

def _read_firefox_history(db_path: str, since_timestamp: Optional[float]) -> List[Dict]:
    """Read a Firefox places.sqlite file."""
    urls: List[Dict] = []
    pid = os.getpid()
    temp_db = f"/tmp/lg_firefox_{pid}_{abs(hash(db_path)) % 100000}.db"

    try:
        shutil.copy2(db_path, temp_db)
        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True, timeout=5)
        conn.row_factory = None

        if since_timestamp:
            # Firefox stores microseconds since Unix epoch
            firefox_ts = int(since_timestamp * 1_000_000)
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_date "
                "FROM moz_places "
                "WHERE visit_count > 0 AND last_visit_date > ? "
                "ORDER BY last_visit_date DESC LIMIT 200",
                (firefox_ts,),
            )
        else:
            cursor = conn.execute(
                "SELECT url, title, visit_count, last_visit_date "
                "FROM moz_places WHERE visit_count > 0 "
                "ORDER BY last_visit_date DESC LIMIT 200"
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
        try:
            os.remove(temp_db)
        except OSError:
            pass

    return urls


# ---------------------------------------------------------------------------
# Public scan API
# ---------------------------------------------------------------------------

# Cache of which browser DB paths actually exist so we skip glob every cycle.
_known_db_paths: Optional[List[tuple]] = None  # list of (browser_key, db_path, is_firefox)
_known_db_paths_built_at: float = 0.0
_DB_PATH_CACHE_TTL = 60.0  # re-scan filesystem for new browsers every 60 s


def _build_db_path_list() -> List[tuple]:
    """Return list of (browser_key, db_path, is_firefox) for all found DBs."""
    found = []
    for bkey in ('chrome', 'chromium', 'brave', 'edge'):
        for p in _get_browser_db_path(bkey):
            found.append((bkey, p, False))
    for p in _get_browser_db_path('firefox'):
        found.append(('firefox', p, True))
    log.debug("Browser DB discovery: %d database(s) found", len(found))
    return found


def scan_browser_history(since_timestamp: Optional[float] = None) -> List[Dict]:
    """Scan all available browser histories.

    This is a blocking function. Callers running inside an async event loop
    must wrap it in ``loop.run_in_executor(None, scan_browser_history, ts)``.

    Args:
        since_timestamp: Only return URLs visited after this Unix timestamp.

    Returns:
        List of dicts: url, title, visit_count, last_visited, browser.
    """
    global _known_db_paths, _known_db_paths_built_at

    now = time.time()
    if _known_db_paths is None or (now - _known_db_paths_built_at) > _DB_PATH_CACHE_TTL:
        _known_db_paths = _build_db_path_list()
        _known_db_paths_built_at = now

    if not _known_db_paths:
        return []

    all_urls: List[Dict] = []
    for _bkey, db_path, is_firefox in _known_db_paths:
        if not os.path.isfile(db_path):
            continue
        if is_firefox:
            all_urls.extend(_read_firefox_history(db_path, since_timestamp))
        else:
            all_urls.extend(_read_chrome_history(db_path, since_timestamp))

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
    """Record the agent start time. Call once when monitoring begins."""
    global _agent_start_time
    _agent_start_time = time.time()
    log.info("Browser history monitor start time: %s", time.ctime(_agent_start_time))


def get_new_history() -> List[Dict]:
    """Return URLs visited since the agent started.

    This is a **blocking** function. The dispatcher must call it inside
    ``loop.run_in_executor`` so it does not block the event loop.
    """
    global _last_scan_time, _last_urls
    try:
        urls = scan_browser_history(since_timestamp=_agent_start_time)
        _last_scan_time = time.time()
        _last_urls = urls
        return urls
    except Exception as exc:
        log.error("Error in get_new_history: %s", exc)
        return []