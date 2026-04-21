"""dispatcher.py — Orchestrate monitors and persist canonical events to SQLite.

Change in this version
----------------------
Browser history poll interval reduced from 30 s to 15 s.
The scan itself takes < 50 ms per browser DB so 15 s is safe and makes
history appear in the Network tab noticeably sooner after URLs are visited.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from . import db
from .monitor import browser_history, device_monitor, network_monitor, process_monitor

log = logging.getLogger("lab_guardian.dispatcher")


def _normalize_device(device: dict) -> dict:
    metadata = device.get("metadata") if isinstance(device.get("metadata"), dict) else {}
    return {
        "id": str(device.get("id") or device.get("device_id") or "").strip(),
        "readable_name": device.get("readable_name") or device.get("device_name") or device.get("name"),
        "message": device.get("message"),
        "risk_level": (device.get("risk_level") or "normal"),
        "metadata": metadata,
        "device_type": "usb",
    }


def _normalize_process(process: dict) -> dict:
    cpu = process.get("cpu")
    if cpu is None:
        cpu = process.get("cpu_percent")

    memory = process.get("memory")
    if memory is None:
        memory = process.get("memory_mb")

    name = process.get("name")
    if not name:
        name = process.get("process_name")

    return {
        "pid": process.get("pid"),
        "name": name,
        "label": process.get("label"),
        "cpu": cpu,
        "memory": memory,
        "status": process.get("status") or "running",
        "risk_level": process.get("risk_level"),
        "category": process.get("category"),
    }


def _normalize_terminal(event: dict, event_type: str, ts: Optional[float]) -> dict:
    detected_at = event.get("detected_at")
    if not detected_at:
        detected_at = datetime.utcnow().isoformat()

    return {
        "id": event.get("id"),
        "event_type": event_type,
        "tool": event.get("tool") or "unknown",
        "detected_at": str(detected_at),
        "pid": event.get("pid") if event.get("pid") is not None else 0,
        "full_command": event.get("full_command") or "",
        "remote_ip": event.get("remote_ip") or "",
        "remote_port": event.get("remote_port") if event.get("remote_port") is not None else 0,
        "remote_host": event.get("remote_host") or "",
        "message": event.get("message") or "",
        "risk_level": event.get("risk_level") or "low",
    }


def _normalize_browser_entry(entry: dict) -> dict:
    last_visited = entry.get("last_visited")
    if last_visited is None:
        last_visited = entry.get("last_visit")

    try:
        if last_visited is not None:
            last_visited = float(last_visited)
            # If stored in milliseconds, convert to seconds.
            if last_visited > 1e10:
                last_visited = last_visited / 1000.0
    except (TypeError, ValueError):
        last_visited = None

    try:
        visit_count = int(entry.get("visit_count") or 1)
    except (TypeError, ValueError):
        visit_count = 1

    return {
        "url": entry.get("url"),
        "title": entry.get("title"),
        "visit_count": visit_count,
        "last_visited": last_visited,
        "browser": entry.get("browser"),
    }


async def run(
    session_id: str,
    roll_no: str,
    lab_no: str,
    stop_event: Optional[asyncio.Event] = None,
):
    """Start all monitors and persist event stream to local DB."""

    if stop_event is None:
        stop_event = asyncio.Event()

    _queue: asyncio.Queue = asyncio.Queue(maxsize=4096)

    async def enqueue(event: dict):
        if _queue.full():
            try:
                _queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await _queue.put(event)

    async def drain():
        while True:
            evt = await _queue.get()
            event_type = evt.get("type")
            data = evt.get("data")
            ts = evt.get("ts")
            meta = evt.get("meta") or {}

            if event_type == "devices_snapshot" and isinstance(data, dict):
                usb_devices = []
                for raw in data.get("usb", []) or []:
                    if not isinstance(raw, dict):
                        continue
                    normalized = _normalize_device(raw)
                    if normalized.get("id"):
                        usb_devices.append(normalized)
                db.replace_devices(session_id, roll_no, usb_devices)

            elif event_type == "device_connected" and isinstance(data, dict):
                device_type = str(data.get("type") or data.get("device_type") or "").lower()
                if device_type == "usb":
                    normalized = _normalize_device(data)
                    if meta.get("risk_level") is not None and normalized.get("risk_level") is None:
                        normalized["risk_level"] = meta.get("risk_level")
                    if meta.get("message") is not None and normalized.get("message") is None:
                        normalized["message"] = meta.get("message")
                    if normalized.get("id"):
                        db.upsert_device(session_id, roll_no, normalized)

            elif event_type == "device_disconnected" and isinstance(data, dict):
                device_id = data.get("id") or data.get("device_id")
                if device_id:
                    db.remove_device(session_id, roll_no, str(device_id))

            elif event_type == "browser_history" and isinstance(data, list):
                for raw in data:
                    if not isinstance(raw, dict):
                        continue
                    normalized = _normalize_browser_entry(raw)
                    if normalized.get("url"):
                        db.upsert_browser_history(session_id, roll_no, normalized)

            elif event_type == "process_snapshot" and isinstance(data, list):
                filtered = []
                for raw in data:
                    if not isinstance(raw, dict):
                        continue
                    normalized = _normalize_process(raw)
                    risk = str(normalized.get("risk_level") or "").lower()
                    if risk in {"high", "medium"}:
                        filtered.append(normalized)
                db.replace_processes(session_id, roll_no, filtered)

            elif event_type == "process_new" and isinstance(data, dict):
                merged = dict(data)
                if meta.get("risk_level") is not None and merged.get("risk_level") is None:
                    merged["risk_level"] = meta.get("risk_level")
                if meta.get("category") is not None and merged.get("category") is None:
                    merged["category"] = meta.get("category")
                normalized = _normalize_process(merged)
                risk = str(normalized.get("risk_level") or "").lower()
                if risk in {"high", "medium"}:
                    db.upsert_process(session_id, roll_no, normalized)

            elif event_type == "process_update" and isinstance(data, dict):
                merged = dict(data)
                if meta.get("risk_level") is not None and merged.get("risk_level") is None:
                    merged["risk_level"] = meta.get("risk_level")
                if meta.get("category") is not None and merged.get("category") is None:
                    merged["category"] = meta.get("category")
                db.update_process(session_id, roll_no, _normalize_process(merged))

            elif event_type == "process_end" and isinstance(data, dict):
                if data.get("pid") is not None:
                    db.delete_process(session_id, roll_no, data.get("pid"))

            elif event_type == "terminal_request" and isinstance(data, dict):
                merged = dict(data)
                if meta.get("risk_level") is not None and merged.get("risk_level") is None:
                    merged["risk_level"] = meta.get("risk_level")
                if meta.get("message") is not None and merged.get("message") is None:
                    merged["message"] = meta.get("message")
                normalized = _normalize_terminal(merged, "terminal_request", ts)
                db.save_terminal_event(session_id, roll_no, normalized)

            elif event_type == "terminal_command" and isinstance(data, dict):
                merged = dict(data)
                if meta.get("risk_level") is not None and merged.get("risk_level") is None:
                    merged["risk_level"] = meta.get("risk_level")
                if meta.get("message") is not None and merged.get("message") is None:
                    merged["message"] = meta.get("message")
                normalized = _normalize_terminal(merged, "terminal_command", ts)
                db.save_terminal_event(session_id, roll_no, normalized)

            elif event_type == "terminal_events_snapshot" and isinstance(data, list):
                events = []
                for raw in data:
                    if not isinstance(raw, dict):
                        continue
                    raw_type = raw.get("event_type") or "terminal_command"
                    events.append(_normalize_terminal(raw, raw_type, ts))
                db.replace_terminal_events(session_id, roll_no, events)

            else:
                log.debug("Unrecognized event type: %s", event_type)

    async def browser_history_monitor(send_fn):
        """Monitor browser history.

        ``browser_history.get_new_history()`` is a blocking function that does
        disk I/O (shutil.copy2 + sqlite3 queries). It is offloaded to the
        default thread executor so the async event loop is never blocked.

        Poll interval: 15 s (reduced from 30 s) — the copy+query of a single
        browser DB takes < 50 ms, so 15 s is safe and makes history appear
        in the Network tab noticeably sooner.
        """
        browser_history.initialize_agent_start_time()
        log.info("Browser history monitor started (poll interval: 15 s)")
        loop = asyncio.get_event_loop()

        while True:
            try:
                # Run the blocking scan in a thread — does NOT block the loop.
                new_urls = await loop.run_in_executor(
                    None, browser_history.get_new_history
                )
                if new_urls:
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
            except Exception as exc:
                log.error("Browser history scan error: %s", exc, exc_info=True)

            # 15 s between browser scans — reduced from 30 s
            await asyncio.sleep(15)

    async def stop_waiter():
        await stop_event.wait()

    tasks = [
        asyncio.create_task(process_monitor.run(enqueue), name="proc"),
        asyncio.create_task(device_monitor.run(enqueue), name="dev"),
        asyncio.create_task(network_monitor.run(enqueue), name="net"),
        asyncio.create_task(browser_history_monitor(enqueue), name="browser"),
        asyncio.create_task(drain(), name="drain"),
        asyncio.create_task(stop_waiter(), name="stop"),
    ]

    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception() if not task.cancelled() else None
            if exc:
                log.error("Task %s failed: %s", task.get_name(), exc)
    except asyncio.CancelledError:
        log.info("Dispatcher cancelled")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("All monitor tasks stopped")