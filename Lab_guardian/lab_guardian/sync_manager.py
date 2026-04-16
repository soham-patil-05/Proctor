"""sync_manager.py - Manages synchronization of local data to backend server."""

import asyncio
import logging
import time
import json
import requests
from datetime import datetime, timezone

log = logging.getLogger("lab_guardian.sync")

class SyncManager:
    """Handles uploading unsynced logs from local SQLite to backend."""
    
    def __init__(self, local_db, backend_url=None):
        self.local_db = local_db
        self.backend_url = backend_url or "http://localhost:8000"
        self.sync_interval = 30  # Check every 30 seconds
        self.running = False
        self.sync_enabled = False
        self.last_sync_time = None
        self.total_synced = 0
    
    async def start(self, session_id):
        """Start the sync manager background task."""
        self.running = True
        self.session_id = session_id
        
        log.info(f"Sync manager started for session {session_id}")
        
        while self.running:
            try:
                if self.sync_enabled:
                    await self.sync_data()
                await asyncio.sleep(self.sync_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Sync manager error: {e}", exc_info=True)
                await asyncio.sleep(self.sync_interval)
    
    def stop(self):
        """Stop the sync manager."""
        self.running = False
        log.info("Sync manager stopped")
    
    def enable_sync(self):
        """Enable automatic syncing."""
        self.sync_enabled = True
        log.info("Sync enabled")
    
    def disable_sync(self):
        """Disable automatic syncing."""
        self.sync_enabled = False
        log.info("Sync disabled")
    
    async def sync_data(self):
        """Upload all unsynced data to backend."""
        try:
            # Check internet connectivity first
            if not self.check_internet():
                log.debug("No internet connection, skipping sync")
                return
            
            log.info("Starting data sync...")
            
            # Collect all unsynced data
            sync_data = {
                "session_id": self.session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "processes": self.local_db.get_unsynced_processes(self.session_id),
                "devices": self.local_db.get_unsynced_devices(self.session_id),
                "terminal_events": self.local_db.get_unsynced_terminal_events(self.session_id),
                "browser_history": self.local_db.get_unsynced_browser_history(self.session_id),
            }
            
            # Check if there's anything to sync
            total_records = (
                len(sync_data["processes"]) +
                len(sync_data["devices"]) +
                len(sync_data["terminal_events"]) +
                len(sync_data["browser_history"])
            )
            
            if total_records == 0:
                log.debug("No unsynced data")
                return
            
            # Send to backend
            success = await self.send_to_backend(sync_data)
            
            if success:
                # Mark data as synced
                self.local_db.mark_as_synced("local_processes", self.session_id)
                self.local_db.mark_as_synced("local_devices", self.session_id)
                self.local_db.mark_as_synced("local_terminal_events", self.session_id)
                self.local_db.mark_as_synced("local_browser_history", self.session_id)
                
                self.total_synced += total_records
                self.last_sync_time = datetime.now()
                
                log.info(f"Sync successful: {total_records} records uploaded")
            else:
                log.warning("Sync failed - will retry next interval")
        
        except Exception as e:
            log.error(f"Sync error: {e}", exc_info=True)
    
    def check_internet(self):
        """Check if internet is available."""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False
    
    async def send_to_backend(self, data):
        """Send data to backend server."""
        try:
            endpoint = f"{self.backend_url}/api/logs/receive"
            
            # Use requests in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    endpoint,
                    json=data,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
            )
            
            if response.status_code == 200:
                return True
            else:
                log.error(f"Backend returned status {response.status_code}: {response.text}")
                return False
        
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to send data to backend: {e}")
            return False
    
    def get_sync_status(self):
        """Get current sync status for UI display."""
        return {
            "enabled": self.sync_enabled,
            "last_sync": self.last_sync_time,
            "total_synced": self.total_synced,
            "internet_available": self.check_internet()
        }
