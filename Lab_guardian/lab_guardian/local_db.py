"""local_db.py - Local SQLite database for offline-first Lab Guardian agent."""

import sqlite3
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("lab_guardian.local_db")

class LocalDatabase:
    """Manages local SQLite database for storing monitoring data offline."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            # Store in user's home directory
            home = Path.home()
            db_dir = home / ".lab_guardian"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "exam_data.db"
        
        self.db_path = str(db_path)
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        
        # Exam sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exam_sessions (
                id TEXT PRIMARY KEY,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL,
                secret_key_verified INTEGER DEFAULT 0,
                synced INTEGER DEFAULT 0
            )
        """)
        
        # Processes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                pid INTEGER NOT NULL,
                process_name TEXT NOT NULL,
                cpu_percent REAL DEFAULT 0,
                memory_mb REAL DEFAULT 0,
                status TEXT DEFAULT 'running',
                risk_level TEXT DEFAULT 'normal',
                category TEXT,
                label TEXT,
                is_incognito INTEGER DEFAULT 0,
                timestamp REAL NOT NULL,
                synced INTEGER DEFAULT 0,
                UNIQUE(session_id, pid, timestamp)
            )
        """)
        
        # Devices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                device_name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                readable_name TEXT,
                risk_level TEXT DEFAULT 'normal',
                message TEXT,
                metadata TEXT,
                connected_at REAL NOT NULL,
                disconnected_at REAL,
                synced INTEGER DEFAULT 0
            )
        """)
        
        # Network info table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_network (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                ip_address TEXT,
                gateway TEXT,
                dns TEXT,
                active_connections INTEGER,
                timestamp REAL NOT NULL,
                synced INTEGER DEFAULT 0
            )
        """)
        
        # Terminal events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_terminal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                remote_ip TEXT,
                remote_host TEXT,
                remote_port INTEGER,
                pid INTEGER,
                event_type TEXT NOT NULL,
                full_command TEXT,
                risk_level TEXT DEFAULT 'medium',
                message TEXT,
                detected_at REAL NOT NULL,
                synced INTEGER DEFAULT 0
            )
        """)
        
        # Browser history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_browser_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                visit_count INTEGER DEFAULT 1,
                last_visited REAL NOT NULL,
                browser TEXT,
                synced INTEGER DEFAULT 0,
                UNIQUE(session_id, url)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_session ON local_processes(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_synced ON local_processes(synced)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_session ON local_devices(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terminal_session ON local_terminal_events(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_browser_session ON local_browser_history(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_roll ON exam_sessions(roll_no)")
        
        self.conn.commit()
        log.info(f"Local database initialized at {self.db_path}")
    
    def create_exam_session(self, session_id, roll_no, lab_no):
        """Create a new exam session."""
        cursor = self.conn.cursor()
        start_time = datetime.now(timezone.utc).timestamp()
        
        cursor.execute("""
            INSERT OR REPLACE INTO exam_sessions 
            (id, roll_no, lab_no, start_time)
            VALUES (?, ?, ?, ?)
        """, (session_id, roll_no, lab_no, start_time))
        
        self.conn.commit()
        log.info(f"Created exam session: {session_id} for {roll_no} in {lab_no}")
        return start_time
    
    def end_exam_session(self, session_id):
        """End an exam session."""
        cursor = self.conn.cursor()
        end_time = datetime.now(timezone.utc).timestamp()
        
        cursor.execute("""
            UPDATE exam_sessions 
            SET end_time = ?, secret_key_verified = 1
            WHERE id = ?
        """, (end_time, session_id))
        
        self.conn.commit()
        log.info(f"Ended exam session: {session_id}")
    
    def get_active_session(self):
        """Get the currently active exam session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM exam_sessions 
            WHERE end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    # Process methods
    def insert_process(self, session_id, process_data, timestamp=None):
        """Insert a process record."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).timestamp()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO local_processes
            (session_id, pid, process_name, cpu_percent, memory_mb, status,
             risk_level, category, label, is_incognito, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            process_data.get('pid'),
            process_data.get('name'),
            process_data.get('cpu', 0),
            process_data.get('memory', 0),
            process_data.get('status', 'running'),
            process_data.get('risk_level', 'normal'),
            process_data.get('category'),
            process_data.get('label'),
            1 if process_data.get('is_incognito') else 0,
            timestamp
        ))
        
        self.conn.commit()
    
    def insert_process_snapshot(self, session_id, processes):
        """Append-only process logging - don't delete old data.
        
        Only inserts new processes that haven't been seen before.
        No resource consumption stats (CPU/memory) - just process names and risk.
        """
        timestamp = datetime.now(timezone.utc).timestamp()
        cursor = self.conn.cursor()
        
        # Group processes by name to handle duplicates in single snapshot
        grouped = {}
        for proc in processes:
            name = proc.get('name', 'Unknown')
            if name not in grouped:
                grouped[name] = {
                    'pid': proc.get('pid'),
                    'risk_level': 'normal',
                    'category': proc.get('category'),
                    'label': proc.get('label'),
                    'is_incognito': proc.get('is_incognito', False),
                    'count': 0
                }
            g = grouped[name]
            g['count'] += 1
            # Keep highest risk
            if proc.get('risk_level') == 'high' or g['risk_level'] == 'high':
                g['risk_level'] = 'high'
            elif proc.get('risk_level') == 'medium':
                g['risk_level'] = 'medium'
            # Track if any instance is incognito
            if proc.get('is_incognito'):
                g['is_incognito'] = True
        
        # Insert only new processes (append-only)
        for name, data in grouped.items():
            process_name = f"{name} (x{data['count']})" if data['count'] > 1 else name
            
            # Check if this process name already exists for this session
            cursor.execute("""
                SELECT id FROM local_processes 
                WHERE session_id = ? AND process_name = ?
            """, (session_id, process_name))
            
            if cursor.fetchone():
                continue  # Skip if already logged
            
            cursor.execute("""
                INSERT INTO local_processes
                (session_id, pid, process_name, cpu_percent, memory_mb, status,
                 risk_level, category, label, is_incognito, timestamp)
                VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                data['pid'],
                process_name,
                'running',
                data['risk_level'],
                data['category'],
                data['label'],
                1 if data['is_incognito'] else 0,
                timestamp
            ))
        
        self.conn.commit()
    
    # Device methods
    def insert_device(self, session_id, device_data):
        """Insert or update device - avoid duplicates per session."""
        cursor = self.conn.cursor()
        connected_at = datetime.now(timezone.utc).timestamp()
        device_id = device_data.get('id')
        
        # Check if device already exists for this session
        cursor.execute("""
            SELECT id FROM local_devices 
            WHERE session_id = ? AND device_id = ?
        """, (session_id, device_id))
        
        if cursor.fetchone():
            # Device already exists, don't duplicate
            return
        
        cursor.execute("""
            INSERT INTO local_devices
            (session_id, device_id, device_name, device_type, readable_name,
             risk_level, message, metadata, connected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            device_id,
            device_data.get('name'),
            device_data.get('type', 'usb'),
            device_data.get('readable_name'),
            device_data.get('risk_level', 'normal'),
            device_data.get('message'),
            json.dumps(device_data.get('metadata', {})),
            connected_at
        ))
        
        self.conn.commit()
    
    # Network methods
    def insert_network_info(self, session_id, network_data):
        """Append network info - keep history of network changes."""
        timestamp = datetime.now(timezone.utc).timestamp()
        cursor = self.conn.cursor()
        
        ip = network_data.get('ip', '')
        
        # Check if this exact network state already exists recently (within 1 min)
        one_min_ago = timestamp - 60
        cursor.execute("""
            SELECT id FROM local_network 
            WHERE session_id = ? AND ip_address = ? AND timestamp > ?
        """, (session_id, ip, one_min_ago))
        
        if cursor.fetchone():
            return  # Skip if same IP logged recently
        
        cursor.execute("""
            INSERT INTO local_network
            (session_id, ip_address, gateway, dns, active_connections, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            ip,
            network_data.get('gateway'),
            json.dumps(network_data.get('dns', [])),
            network_data.get('activeConnections', 0),
            timestamp
        ))
        
        self.conn.commit()
    
    # Terminal methods
    def insert_terminal_event(self, session_id, event_data):
        """Insert a terminal event - append-only, exact match deduplication."""
        detected_at = datetime.now(timezone.utc).timestamp()
        cursor = self.conn.cursor()
        
        tool = event_data.get('tool', 'unknown')
        cmd = event_data.get('full_command', '')
        host = event_data.get('remote_host', event_data.get('remote_ip', ''))
        
        # Check for exact duplicate (same tool, command, host, time within 1 second)
        time_key = int(detected_at)
        cursor.execute("""
            SELECT id FROM local_terminal_events 
            WHERE session_id = ? AND tool = ? AND remote_host = ? 
            AND full_command = ? AND CAST(detected_at AS INTEGER) = ?
        """, (session_id, tool, host, cmd, time_key))
        
        if cursor.fetchone():
            return  # Exact duplicate exists
        
        cursor.execute("""
            INSERT INTO local_terminal_events
            (session_id, tool, remote_ip, remote_host, remote_port, pid,
             event_type, full_command, risk_level, message, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            tool,
            event_data.get('remote_ip'),
            host,
            event_data.get('remote_port'),
            event_data.get('pid'),
            event_data.get('event_type', 'terminal_request'),
            cmd,
            event_data.get('risk_level', 'medium'),
            event_data.get('message'),
            detected_at
        ))
        
        self.conn.commit()
    
    # Browser history methods
    def insert_browser_history(self, session_id, urls):
        """Insert browser history - append-only, skip existing URLs."""
        if not urls:
            return
            
        cursor = self.conn.cursor()
        inserted = 0
        
        for url_data in urls:
            url = url_data.get('url')
            if not url:
                continue
                
            # Check if URL already exists
            cursor.execute("""
                SELECT id FROM local_browser_history 
                WHERE session_id = ? AND url = ?
            """, (session_id, url))
            
            if cursor.fetchone():
                continue  # Skip existing URLs (append-only)
            
            # Insert new URL only
            cursor.execute("""
                INSERT INTO local_browser_history
                (session_id, url, title, visit_count, last_visited, browser)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                url,
                url_data.get('title', '')[:200],
                url_data.get('visit_count', 1),
                url_data.get('last_visited', datetime.now(timezone.utc).timestamp()),
                url_data.get('browser', 'Unknown')
            ))
            inserted += 1
        
        self.conn.commit()
        return {'inserted': inserted}
    
    # Sync methods
    def get_unsynced_processes(self, session_id):
        """Get all unsynced processes for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_processes
            WHERE session_id = ? AND synced = 0
        """, (session_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_unsynced_devices(self, session_id):
        """Get all unsynced devices for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_devices
            WHERE session_id = ? AND synced = 0
        """, (session_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_unsynced_terminal_events(self, session_id):
        """Get all unsynced terminal events for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_terminal_events
            WHERE session_id = ? AND synced = 0
        """, (session_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_unsynced_browser_history(self, session_id):
        """Get all unsynced browser history for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_browser_history
            WHERE session_id = ? AND synced = 0
        """, (session_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def mark_as_synced(self, table_name, session_id):
        """Mark all records for a session as synced."""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            UPDATE {table_name}
            SET synced = 1
            WHERE session_id = ?
        """, (session_id,))
        
        self.conn.commit()
    
    # Query methods for UI
    def get_recent_processes(self, session_id, limit=50):
        """Get recent processes for UI display."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_processes
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_browser_history(self, session_id, limit=50):
        """Get recent browser history for UI display."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_browser_history
            WHERE session_id = ?
            ORDER BY last_visited DESC
            LIMIT ?
        """, (session_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_terminal_events(self, session_id, limit=50):
        """Get recent terminal events for UI display."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_terminal_events
            WHERE session_id = ?
            ORDER BY detected_at DESC
            LIMIT ?
        """, (session_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_devices(self, session_id):
        """Get all devices for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM local_devices
            WHERE session_id = ?
            ORDER BY connected_at DESC
        """, (session_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self, session_id, max_age_days=30):
        """Clean up very old data after session ends.
        
        Keeps data for 30 days by default - only cleans up after exam is complete.
        This is append-only during the exam, cleanup happens post-session.
        """
        # Check if session is still active - don't cleanup during exam
        active = self.get_active_session()
        if active and active.get('session_id') == session_id:
            return {'skipped': 'session_active'}  # Don't cleanup during exam
        
        cursor = self.conn.cursor()
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
        
        # Clean very old terminal events (only after session ends)
        cursor.execute("""
            DELETE FROM local_terminal_events 
            WHERE session_id = ? AND detected_at < ?
        """, (session_id, cutoff))
        terminal_deleted = cursor.rowcount
        
        # Clean very old browser history (only after session ends)
        cursor.execute("""
            DELETE FROM local_browser_history 
            WHERE session_id = ? AND last_visited < ?
        """, (session_id, cutoff))
        browser_deleted = cursor.rowcount
        
        # Vacuum to reclaim space
        cursor.execute("VACUUM")
        
        self.conn.commit()
        
        if terminal_deleted > 0 or browser_deleted > 0:
            log.info(f"Post-session cleanup: {terminal_deleted} terminal events, {browser_deleted} browser URLs (> {max_age_days} days)")
        
        return {'terminal_deleted': terminal_deleted, 'browser_deleted': browser_deleted}
    
    def get_db_size(self):
        """Get current database file size in bytes."""
        import os
        try:
            return os.path.getsize(self.db_path)
        except:
            return 0
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            log.info("Database connection closed")
