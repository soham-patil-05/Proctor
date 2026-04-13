#!/usr/bin/env python3
"""Test script to debug Firefox history reading."""

import os
import sqlite3
import time
from glob import glob

print("=== Firefox History Debug ===\n")

# Find Firefox databases
firefox_paths = [
    os.path.expanduser('~/.mozilla/firefox/*/places.sqlite'),
    os.path.expanduser('~/snap/firefox/common/.mozilla/firefox/*/places.sqlite'),
]

found_dbs = []
for path_template in firefox_paths:
    matches = glob(path_template)
    found_dbs.extend(matches)

if not found_dbs:
    print("❌ No Firefox databases found!")
    print("\nTry installing Firefox and visiting some websites first.")
    exit(1)

print(f"✅ Found {len(found_dbs)} Firefox database(s):\n")

for db_path in found_dbs:
    print(f"Database: {db_path}")
    print(f"Size: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB")
    
    try:
        # Copy to avoid locking
        import shutil
        temp_db = f"/tmp/test_firefox_{os.getpid()}.db"
        shutil.copy2(db_path, temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Check total URLs
        cursor.execute("SELECT count(*) FROM moz_places WHERE visit_count > 0")
        total_urls = cursor.fetchone()[0]
        print(f"Total URLs with visits: {total_urls}")
        
        # Get most recent URLs
        cursor.execute("""
            SELECT url, title, visit_count, last_visit_date
            FROM moz_places
            WHERE visit_count > 0
            ORDER BY last_visit_date DESC
            LIMIT 5
        """)
        
        print("\nMost recent 5 URLs:")
        for i, (url, title, visit_count, moz_time) in enumerate(cursor.fetchall(), 1):
            print(f"\n{i}. {url}")
            print(f"   Title: {title or 'N/A'}")
            print(f"   Visits: {visit_count}")
            print(f"   Firefox time (microseconds): {moz_time}")
            
            if moz_time and moz_time > 0:
                unix_ts = moz_time / 1000000.0
                print(f"   Unix timestamp (seconds): {unix_ts}")
                print(f"   Human readable: {time.ctime(unix_ts)}")
                
                # Check if it's after agent start time (example: 5 minutes ago)
                five_min_ago = time.time() - 300
                print(f"   After 5 min ago? {unix_ts > five_min_ago}")
        
        conn.close()
        os.remove(temp_db)
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60 + "\n")

# Test with timestamp filter
print("\n=== Testing Timestamp Filter ===")
agent_start_time = time.time() - 300  # 5 minutes ago
print(f"Agent start time: {time.ctime(agent_start_time)}")
print(f"Agent start time (Unix): {agent_start_time}")
print(f"Firefox format (microseconds): {int(agent_start_time * 1000000)}\n")

if found_dbs:
    try:
        import shutil
        temp_db = f"/tmp/test_firefox_{os.getpid()}.db"
        shutil.copy2(found_dbs[0], temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        firefox_timestamp = int(agent_start_time * 1000000)
        cursor.execute("""
            SELECT url, title, visit_count, last_visit_date
            FROM moz_places
            WHERE visit_count > 0 AND last_visit_date > ?
            ORDER BY last_visit_date DESC
            LIMIT 10
        """, (firefox_timestamp,))
        
        rows = cursor.fetchall()
        print(f"URLs visited after agent start: {len(rows)}")
        
        for i, (url, title, visit_count, moz_time) in enumerate(rows, 1):
            unix_ts = moz_time / 1000000.0 if moz_time else 0
            print(f"{i}. {url[:80]}... ({time.ctime(unix_ts)})")
        
        conn.close()
        os.remove(temp_db)
        
    except Exception as e:
        print(f"❌ Error: {e}")
