"""browser_history.py — Scan browser history databases for visited URLs.

Supports:
  - Google Chrome / Chromium
  - Mozilla Firefox
  - Microsoft Edge
  - Brave

Extracts full URLs with visit timestamps and visit counts.
"""

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import List, Dict

log = logging.getLogger("lab_guardian.monitor.browser_history")

# Browser history database locations
BROWSER_PATHS = {
    'chrome': {
        'linux': ['~/.config/google-chrome/Default/History'],
        'windows': ['~/AppData/Local/Google/Chrome/User Data/Default/History'],
        'name': 'Google Chrome'
    },
    'chromium': {
        'linux': ['~/.config/chromium/Default/History', '~/snap/chromium/common/chromium/Default/History'],
        'windows': ['~/AppData/Local/Chromium/User Data/Default/History'],
        'name': 'Chromium'
    },
    'brave': {
        'linux': ['~/.config/BraveSoftware/Brave-Browser/Default/History', '~/snap/brave/common/.config/BraveSoftware/Brave-Browser/Default/History'],
        'windows': ['~/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/History'],
        'name': 'Brave'
    },
    'edge': {
        'linux': ['~/.config/microsoft-edge/Default/History'],
        'windows': ['~/AppData/Local/Microsoft/Edge/User Data/Default/History'],
        'name': 'Microsoft Edge'
    },
    'firefox': {
        'linux': ['~/.mozilla/firefox/*/places.sqlite', '~/snap/firefox/common/.mozilla/firefox/*/places.sqlite'],
        'windows': ['~/AppData/Roaming/Mozilla/Firefox/Profiles/*/places.sqlite'],
        'name': 'Mozilla Firefox'
    }
}


def _get_browser_db_path(browser_key: str) -> List[str]:
    """Get the database path(s) for a browser."""
    import platform
    browser_info = BROWSER_PATHS.get(browser_key, {})
    
    os_name = platform.system().lower()
    if 'windows' in os_name:
        path_templates = browser_info.get('windows', [])
    else:
        path_templates = browser_info.get('linux', [])
        
    if not isinstance(path_templates, list):
        path_templates = [path_templates] if path_templates else []
        
    results = []
    from glob import glob
    for template in path_templates:
        path = os.path.expanduser(template)
        if '*' in path:
            results.extend(glob(path))
        elif os.path.exists(path):
            results.append(path)
            
    return results


def _read_chrome_history(db_path: str, since_timestamp: float = None) -> List[Dict]:
    """Read Chrome/Chromium/Brave/Edge history database.
    
    Returns list of dicts with url, title, visit_count, last_visit_time
    """
    urls = []
    try:
        # Copy DB to avoid locking issues
        import shutil
        temp_db = f"/tmp/browser_history_{os.getpid()}.db"
        shutil.copy2(db_path, temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Chrome stores time as microseconds since Jan 1, 1601
        # Convert to Unix timestamp (seconds since Jan 1, 1970)
        chrome_epoch_offset = 11644473600000000  # microseconds
        
        query = """
            SELECT url, title, visit_count, last_visit_time 
            FROM urls 
            ORDER BY last_visit_time DESC
            LIMIT 100
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for row in rows:
            url, title, visit_count, chrome_time = row
            
            # Convert Chrome time to Unix timestamp
            if chrome_time:
                unix_timestamp = (chrome_time - chrome_epoch_offset) / 1000000
            else:
                unix_timestamp = 0
            
            # Skip if older than our last check
            if since_timestamp and unix_timestamp < since_timestamp:
                continue
            
            urls.append({
                'url': url,
                'title': title or '',
                'visit_count': visit_count or 1,
                'last_visited': unix_timestamp,
                'browser': 'Chrome'
            })
        
        conn.close()
        os.remove(temp_db)
        
    except Exception as e:
        log.debug(f"Error reading Chrome history from {db_path}: {e}")
    
    return urls


def _read_firefox_history(db_path: str, since_timestamp: float = None) -> List[Dict]:
    """Read Firefox history database (places.sqlite).
    
    Returns list of dicts with url, title, visit_count, last_visit_date
    """
    urls = []
    try:
        import shutil
        temp_db = f"/tmp/browser_history_{os.getpid()}.db"
        shutil.copy2(db_path, temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Firefox stores time in microseconds since Jan 1, 1970
        query = """
            SELECT p.url, p.title, p.visit_count, p.last_visit_date
            FROM moz_places p
            WHERE p.visit_count > 0
            ORDER BY p.last_visit_date DESC
            LIMIT 100
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for row in rows:
            url, title, visit_count, moz_time = row
            
            # Convert Firefox time (microseconds) to seconds
            if moz_time:
                unix_timestamp = moz_time / 1000000
            else:
                unix_timestamp = 0
            
            # Skip if older than our last check
            if since_timestamp and unix_timestamp < since_timestamp:
                continue
            
            urls.append({
                'url': url,
                'title': title or '',
                'visit_count': visit_count or 1,
                'last_visited': unix_timestamp,
                'browser': 'Firefox'
            })
        
        conn.close()
        os.remove(temp_db)
        
    except Exception as e:
        log.debug(f"Error reading Firefox history from {db_path}: {e}")
    
    return urls


def scan_browser_history(since_timestamp: float = None) -> List[Dict]:
    """Scan all available browser histories.
    
    Args:
        since_timestamp: Only return URLs visited after this Unix timestamp
        
    Returns:
        List of dicts with url, title, visit_count, last_visited, browser
    """
    all_urls = []
    
    # Chrome-based browsers
    for browser_key in ['chrome', 'chromium', 'brave', 'edge']:
        db_paths = _get_browser_db_path(browser_key)
        log.info(f"Looking for {BROWSER_PATHS[browser_key]['name']}: found {len(db_paths)} database(s)")
        for db_path in db_paths:
            if os.path.exists(db_path):
                log.info(f"Scanning {BROWSER_PATHS[browser_key]['name']} history from {db_path}")
                urls = _read_chrome_history(db_path, since_timestamp)
                log.info(f"  -> Found {len(urls)} URLs")
                all_urls.extend(urls)
            else:
                log.debug(f"  -> Database not found: {db_path}")
    
    # Firefox
    firefox_paths = _get_browser_db_path('firefox')
    log.info(f"Looking for Firefox: found {len(firefox_paths)} database(s)")
    for db_path in firefox_paths:
        if os.path.exists(db_path):
            log.info(f"Scanning Firefox history from {db_path}")
            urls = _read_firefox_history(db_path, since_timestamp)
            log.info(f"  -> Found {len(urls)} URLs")
            all_urls.extend(urls)
        else:
            log.debug(f"  -> Database not found: {db_path}")
    
    # Sort by last visited time (most recent first)
    all_urls.sort(key=lambda x: x['last_visited'], reverse=True)
    
    log.info(f"Total: Found {len(all_urls)} URLs from browser history")
    return all_urls


# Track when the agent started
_agent_start_time = 0
_last_scan_time = 0
_last_urls = []


def initialize_agent_start_time():
    """Set the agent start time. Call this when the agent first starts."""
    global _agent_start_time
    _agent_start_time = time.time()
    log.info(f"Browser history monitor will track URLs visited after: {time.ctime(_agent_start_time)}")


def get_new_history() -> List[Dict]:
    """Get browser history URLs visited AFTER agent started.
    
    Returns:
        List of URL entries visited since agent started
    """
    global _last_scan_time, _last_urls
    
    try:
        # Only get URLs visited after agent started
        current_urls = scan_browser_history(since_timestamp=_agent_start_time)
        
        # Update scan time
        _last_scan_time = time.time()
        
        _last_urls = current_urls
        return current_urls
    except Exception as e:
        log.error(f"Error getting browser history: {e}")
        return []
