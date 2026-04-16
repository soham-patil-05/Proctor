"""dispatcher.py - Orchestrate all monitors with local storage and UI."""

import asyncio
import logging
import time
import uuid

from .local_db import LocalDatabase
from .monitor import process_monitor, device_monitor, network_monitor, browser_history
from .sync_manager import SyncManager

log = logging.getLogger("lab_guardian.dispatcher")


async def run_with_ui(local_db, ui_window, backend_url=None):
    """Start all monitors with local storage and UI updates.
    
    This replaces the old WebSocket-based dispatcher.
    """
    sync_manager = SyncManager(local_db, backend_url)
    session_id = None
    
    # Callback to be set when exam starts
    def set_exam_started(sid, roll_no, lab_no):
        nonlocal session_id
        session_id = sid
        log.info(f"Exam started: {session_id}, {roll_no}, {lab_no}")
        
        # Enable sync manager
        sync_manager.enable_sync()
        
        # Update UI sync indicator
        ui_window.indicator_sync.set_status("Sync", "yellow")
    
    # Connect UI signal
    ui_window.on_exam_started = set_exam_started
    
    # Queue for monitor events
    _queue = asyncio.Queue(maxsize=4096)
    
    async def enqueue(event: dict):
        """Callback given to each monitor - stores to local DB."""
        if _queue.full():
            try:
                _queue.get_nowait()  # drop oldest
            except asyncio.QueueEmpty:
                pass
        await _queue.put(event)
    
    async def store_to_local_db():
        """Forward events from queue → local SQLite + UI."""
        while True:
            evt = await _queue.get()
            
            if not session_id:
                continue
            
            try:
                event_type = evt.get("type")
                data = evt.get("data")
                
                # Store to local database based on event type
                if event_type == "process_snapshot":
                    local_db.insert_process_snapshot(session_id, data)
                    # Update UI
                    processes = local_db.get_recent_processes(session_id, limit=50)
                    ui_window.update_processes.emit(processes)
                
                elif event_type == "process_new" or event_type == "process_update":
                    local_db.insert_process(session_id, data)
                    processes = local_db.get_recent_processes(session_id, limit=50)
                    ui_window.update_processes.emit(processes)
                
                elif event_type == "device_connected":
                    local_db.insert_device(session_id, data)
                    devices = local_db.get_devices(session_id)
                    ui_window.update_devices.emit(devices)
                
                elif event_type == "devices_snapshot":
                    for dev in data.get("usb", []):
                        local_db.insert_device(session_id, dev)
                    devices = local_db.get_devices(session_id)
                    ui_window.update_devices.emit(devices)
                
                elif event_type == "network_snapshot":
                    local_db.insert_network_info(session_id, data)
                
                elif event_type == "terminal_request" or event_type == "terminal_command":
                    local_db.insert_terminal_event(session_id, data)
                    terminal_events = local_db.get_recent_terminal_events(session_id, limit=50)
                    ui_window.update_terminal.emit(terminal_events)
                
                elif event_type == "browser_history":
                    if isinstance(data, list):
                        local_db.insert_browser_history(session_id, data)
                        urls = local_db.get_recent_browser_history(session_id, limit=50)
                        ui_window.update_browser.emit(urls)
                
            except Exception as e:
                log.error(f"Error storing to local DB: {e}", exc_info=True)
    
    async def browser_history_monitor_task(send_fn):
        """Monitor browser history for visited URLs."""
        browser_history.initialize_agent_start_time()
        log.info("Browser history monitor started")
        
        while True:
            try:
                new_urls = browser_history.get_new_history()
                if new_urls:
                    log.info(f"Found {len(new_urls)} browser history URLs")
                    await send_fn({
                        "type": "browser_history",
                        "data": new_urls,
                        "ts": time.time(),
                        "meta": {
                            "risk_level": "normal",
                            "category": "browser",
                            "message": f"{len(new_urls)} URL(s) visited during session",
                        },
                    })
            except Exception as e:
                log.error(f"Browser history scan error: {e}", exc_info=True)
            
            await asyncio.sleep(10)
    
    # Start sync manager
    sync_task = None
    
    async def start_sync_when_ready():
        """Start sync manager once session is created."""
        while True:
            if session_id:
                await sync_manager.start(session_id)
                break
            await asyncio.sleep(5)
    
    # Launch all concurrently
    tasks = [
        asyncio.create_task(store_to_local_db(), name="store_local"),
        asyncio.create_task(process_monitor.run(enqueue), name="proc"),
        asyncio.create_task(device_monitor.run(enqueue), name="dev"),
        asyncio.create_task(network_monitor.run(enqueue), name="net"),
        asyncio.create_task(browser_history_monitor_task(enqueue), name="browser"),
        asyncio.create_task(start_sync_when_ready(), name="sync"),
    ]
    
    try:
        # Wait until exam session ends
        while not local_db.get_active_session() or \
              local_db.get_active_session().get('end_time') is None:
            await asyncio.sleep(1)
            
            # Update UI periodically with current data
            if session_id:
                processes = local_db.get_recent_processes(session_id, limit=50)
                ui_window.update_processes.emit(processes)
                
                urls = local_db.get_recent_browser_history(session_id, limit=50)
                ui_window.update_browser.emit(urls)
                
                terminal_events = local_db.get_recent_terminal_events(session_id, limit=50)
                ui_window.update_terminal.emit(terminal_events)
                
                devices = local_db.get_devices(session_id)
                ui_window.update_devices.emit(devices)
        
        log.info("Exam session ended")
        
    except asyncio.CancelledError:
        log.info("Dispatcher cancelled")
    finally:
        for t in tasks:
            t.cancel()
        sync_manager.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("All monitor tasks stopped")
