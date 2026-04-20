"""dispatcher.py — Orchestrate monitors and persist events to local SQLite."""

import asyncio
import logging
from typing import Optional

from . import db
from .monitor import process_monitor, device_monitor, network_monitor, browser_history

log = logging.getLogger("lab_guardian.dispatcher")


async def run(session_id: str, roll_no: str, lab_no: str, stop_event: Optional[asyncio.Event] = None):
    """Start all monitors and persist event stream to local DB.

    The monitor orchestration and queue fan-in behavior are intentionally
    preserved from the previous dispatcher implementation.
    """

    if stop_event is None:
        stop_event = asyncio.Event()

    # Keep a local queue so monitors never block on the network
    _queue: asyncio.Queue = asyncio.Queue(maxsize=4096)

    async def enqueue(event: dict):
        """Callback given to each monitor."""
        if _queue.full():
            try:
                _queue.get_nowait()   # drop oldest
            except asyncio.QueueEmpty:
                pass
        await _queue.put(event)

    async def drain():
        """Forward events from local queue to explicit db handlers."""
        while True:
            evt = await _queue.get()
            event_type = evt.get("type")
            data = evt.get("data")
            ts = evt.get("ts")
            meta = evt.get("meta") or {}

            if event_type in {"process_new", "process_update"} and isinstance(data, dict):
                if meta.get("risk_level") is not None and data.get("risk_level") is None:
                    data["risk_level"] = meta.get("risk_level")
                if meta.get("category") is not None and data.get("category") is None:
                    data["category"] = meta.get("category")

            if event_type == "device_connected" and isinstance(data, dict):
                if meta.get("risk_level") is not None and data.get("risk_level") is None:
                    data["risk_level"] = meta.get("risk_level")
                if meta.get("message") is not None and data.get("message") is None:
                    data["message"] = meta.get("message")

            if event_type in {"terminal_request", "terminal_command"} and isinstance(data, dict):
                if meta.get("risk_level") is not None and data.get("risk_level") is None:
                    data["risk_level"] = meta.get("risk_level")
                if meta.get("message") is not None and data.get("message") is None:
                    data["message"] = meta.get("message")

            if event_type == "process_snapshot":
                db.insert_processes(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "process_new":
                db.insert_processes(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "process_update":
                db.insert_processes(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "process_end":
                db.insert_processes(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "devices_snapshot":
                db.insert_devices(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "device_connected":
                db.insert_devices(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "device_disconnected":
                db.insert_devices(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "network_snapshot":
                db.insert_network(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "network_update":
                db.insert_network(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "domain_activity":
                db.insert_domain_activity(session_id, roll_no, lab_no, data, ts)
            elif event_type == "terminal_request":
                db.insert_terminal_event(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "terminal_command":
                db.insert_terminal_event(session_id, roll_no, lab_no, event_type, data, ts)
            elif event_type == "browser_history":
                db.insert_browser_history(session_id, roll_no, lab_no, data, ts)
            else:
                log.warning("Unrecognized event type dropped: %s", event_type)

    async def browser_history_monitor(send_fn):
        """Monitor browser history for visited URLs."""
        import time
        
        # Initialize the agent start time - only track URLs from this point forward
        browser_history.initialize_agent_start_time()
        log.info("Browser history monitor started")
        
        while True:
            try:
                new_urls = browser_history.get_new_history()
                if new_urls:
                    log.info("Persisting %d browser history URLs", len(new_urls))
                    # Send as browser_history event
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
                else:
                    log.debug("No browser history URLs found since agent started")
            except Exception as e:
                log.error(f"Browser history scan error: {e}", exc_info=True)
            
            # Scan every 10 seconds
            await asyncio.sleep(10)

    async def stop_waiter():
        await stop_event.wait()

    # Launch all concurrently
    tasks = [
        asyncio.create_task(process_monitor.run(enqueue), name="proc"),
        asyncio.create_task(device_monitor.run(enqueue), name="dev"),
        asyncio.create_task(network_monitor.run(enqueue), name="net"),
        asyncio.create_task(browser_history_monitor(enqueue), name="browser"),
        asyncio.create_task(drain(), name="drain"),
        asyncio.create_task(stop_waiter(), name="stop"),
    ]

    try:
        # If any task raises or finishes, cancel the rest
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            if t.exception():
                log.error("Task %s failed: %s", t.get_name(), t.exception())
    except asyncio.CancelledError:
        log.info("Dispatcher cancelled")
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("All monitor tasks stopped")
