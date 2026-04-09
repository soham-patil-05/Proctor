"""browser_monitor.py — Track visited websites by reading browser history databases.

Monitors browser history from:
  - Google Chrome / Chromium
  - Mozilla Firefox
  - Microsoft Edge

Reads SQLite history databases and extracts visited URLs/domains.
Runs on Linux (Ubuntu) and Windows.

Emits:
  • domain_activity – visited domains with visit counts
"""

import asyncio
import logging
import os
import platform
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from .. import config

log = logging.getLogger("lab_guardian.monitor.browser")

# Track already-seen URLs to avoid duplicates
_seen_urls: Set[str] = set()
_domain_counter: Dict[str, int] = defaultdict(int)

# Browser history paths
BROWSER_PATHS = {
    'chrome': {
        'linux': '~/.config/google-chrome/Default/History',
        'windows': '~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\History',
    },
    'chromium': {
        'linux': '~/.config/chromium/Default/History',
        'windows': None,
    },
    'edge': {
        'linux': '~/.config/microsoft-edge/Default/History',
        'windows': '~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\History',
    },
    'firefox': {
        'linux': '~/.mozilla/firefox/*/places.sqlite',
        'windows': '~\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles\\*\\places.sqlite',
    },
}


def _expand_path(pattern: str) -> List[Path]:
    """Expand a path pattern (with glob support) to actual files."""
    import glob
    expanded = os.path.expanduser(pattern)
    
    # Handle wildcard patterns (for Firefox profiles)
    if '*' in expanded:
        return [Path(p) for p in glob.glob(expanded)]
    return [Path(expanded)]


def _find_history_files() -> List[Path]:
    """Find all browser history files on the system."""
    history_files = []
    system = platform.system().lower()
    
    for browser, paths in BROWSER_PATHS.items():
        path_pattern = paths.get(system) or paths.get('linux')
        if not path_pattern:
            continue
        
        files = _expand_path(path_pattern)
        for file_path in files:
            if file_path.exists():
                history_files.append(file_path)
                log.debug(f"Found {browser} history: {file_path}")
    
    return history_files


def _extract_domain_from_url(url: str) -> Optional[str]:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.hostname
        if domain:
            # Remove 'www.' prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain.lower()
    except:
        pass
    return None


def _classify_domain(domain: str) -> str:
    """Classify domain risk level."""
    HIGH_RISK_DOMAINS = {
        'chatgpt.com', 'openai.com', 'chegg.com', 'coursehero.com',
        'brainly.com', 'quizlet.com', 'bartleby.com',
        'github.com', 'gitlab.com', 'stackoverflow.com',
    }
    
    if domain.lower() in HIGH_RISK_DOMAINS:
        return 'high'
    return 'normal'


def _read_chrome_history(db_path: Path) -> List[str]:
    """Read Chrome/Chromium/Edge history from SQLite database."""
    urls = []
    try:
        # Copy database to avoid locking issues
        import shutil
        temp_db = Path('/tmp/chrome_history_temp.db')
        shutil.copy2(db_path, temp_db)
        
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        
        # Get recent URLs (last 1 hour)
        # Chrome stores timestamps in microseconds since Jan 1, 1601
        one_hour_ago = int((time.time() - 3600) * 1000000 + 11644473600000000)
        
        cursor.execute("""
            SELECT url, title, last_visit_time, visit_count 
            FROM urls 
            WHERE last_visit_time > ?
            ORDER BY last_visit_time DESC
        """, (one_hour_ago,))
        
        for row in cursor.fetchall():
            url = row[0]
            urls.append(url)
        
        conn.close()
        temp_db.unlink(missing_ok=True)
        
    except Exception as e:
        log.debug(f"Error reading Chrome history from {db_path}: {e}")
    
    return urls


def _read_firefox_history(db_path: Path) -> List[str]:
    """Read Firefox history from places.sqlite database."""
    urls = []
    try:
        import shutil
        temp_db = Path('/tmp/firefox_history_temp.db')
        shutil.copy2(db_path, temp_db)
        
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        
        # Get recent visits (last 1 hour)
        # Firefox stores timestamps in microseconds since Jan 1, 1970
        one_hour_ago = int((time.time() - 3600) * 1000000)
        
        cursor.execute("""
            SELECT DISTINCT p.url 
            FROM moz_places p
            JOIN moz_historyvisits h ON p.id = h.place_id
            WHERE h.visit_date > ?
            ORDER BY h.visit_date DESC
        """, (one_hour_ago,))
        
        for row in cursor.fetchall():
            url = row[0]
            if url and (url.startswith('http://') or url.startswith('https://')):
                urls.append(url)
        
        conn.close()
        temp_db.unlink(missing_ok=True)
        
    except Exception as e:
        log.debug(f"Error reading Firefox history from {db_path}: {e}")
    
    return urls


def _collect_browser_history() -> Dict[str, int]:
    """Collect recent browser history and count domain visits."""
    global _seen_urls, _domain_counter
    
    domain_counts = defaultdict(int)
    history_files = _find_history_files()
    
    if not history_files:
        log.debug("No browser history files found")
        return {}
    
    for history_file in history_files:
        urls = []
        
        # Determine browser type from path
        if 'firefox' in str(history_file).lower() or 'mozilla' in str(history_file).lower():
            urls = _read_firefox_history(history_file)
        else:
            # Chrome, Chromium, Edge all use same format
            urls = _read_chrome_history(history_file)
        
        # Process URLs
        for url in urls:
            # Skip if already seen
            if url in _seen_urls:
                continue
            
            _seen_urls.add(url)
            
            # Extract domain
            domain = _extract_domain_from_url(url)
            if domain:
                # Filter out browser internal pages
                if not any(skip in domain for skip in [
                    'localhost', '127.0.0.1',
                    'chrome', 'mozilla', 'edge',
                    'about', 'extension'
                ]):
                    domain_counts[domain] += 1
    
    return dict(domain_counts)


def _flush_domain_counter() -> List[Dict]:
    """Return accumulated domain counts and reset."""
    global _domain_counter
    
    if not _domain_counter:
        return []
    
    result = [
        {"domain": d, "count": c, "request_count": c}
        for d, c in sorted(_domain_counter.items(), key=lambda x: -x[1])
    ]
    _domain_counter = defaultdict(int)
    return result


async def run(send_fn):
    """Long-running coroutine that monitors browser history."""
    global _domain_counter
    
    log.info("Browser history monitor started")
    last_check_ts = 0.0
    check_interval = 5  # Check every 5 seconds
    
    while True:
        now = time.monotonic()
        
        if now - last_check_ts >= check_interval:
            try:
                # Collect new history entries
                new_domains = await asyncio.get_event_loop().run_in_executor(
                    None, _collect_browser_history
                )
                
                # Add to counter
                for domain, count in new_domains.items():
                    _domain_counter[domain] += count
                
                # Flush every 5 seconds
                domain_data = _flush_domain_counter()
                if domain_data:
                    log.info(f"Browser history: {len(domain_data)} domain(s) visited: {[d['domain'] for d in domain_data[:5]]}")
                    
                    # Classify domains
                    for entry in domain_data:
                        entry["risk_level"] = _classify_domain(entry["domain"])
                    
                    has_high = any(d["risk_level"] == "high" for d in domain_data)
                    await send_fn({
                        "type": "domain_activity",
                        "data": domain_data,
                        "ts": time.time(),
                        "meta": {
                            "risk_level": "high" if has_high else "normal",
                            "category": "network",
                            "message": f"{len(domain_data)} website(s) visited",
                        },
                    })
                
            except Exception as e:
                log.debug(f"Browser history collection error: {e}")
            
            last_check_ts = now
        
        await asyncio.sleep(2)  # Check every 2 seconds
