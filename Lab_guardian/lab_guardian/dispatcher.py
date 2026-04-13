"""dispatcher.py — Orchestrate all monitors and funnel events to WS client."""

import asyncio
import logging

from . import ws_client
from .monitor import process_monitor, device_monitor, network_monitor, browser_history

log = logging.getLogger("lab_guardian.dispatcher")


async def run(session_id: str, student_id: str, token: str):
    """Start all monitors + WS connection; blocks until session ends or Ctrl-C."""

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
        """Forward events from local queue → ws_client.send()."""
        while True:
            evt = await _queue.get()
            await ws_client.send(evt)

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
                    log.info(f"Sending {len(new_urls)} browser history URLs to server")
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

    # Launch all concurrently
    tasks = [
        asyncio.create_task(ws_client.start(session_id, student_id, token), name="ws"),
        asyncio.create_task(process_monitor.run(enqueue), name="proc"),
        asyncio.create_task(device_monitor.run(enqueue), name="dev"),
        asyncio.create_task(network_monitor.run(enqueue), name="net"),
        asyncio.create_task(browser_history_monitor(enqueue), name="browser"),
        asyncio.create_task(drain(), name="drain"),
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
