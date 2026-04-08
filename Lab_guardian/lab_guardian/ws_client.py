"""ws_client.py — Persistent WebSocket connection with reconnect & outbound queue."""

import asyncio
import json
import logging
import random
import time

import websockets
from websockets.exceptions import ConnectionClosed

from . import config

log = logging.getLogger("lab_guardian.ws")

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

_ws = None
_send_queue: asyncio.Queue | None = None
_stop_event: asyncio.Event | None = None


async def start(session_id: str, student_id: str, token: str):
    """Launch reader + writer tasks; blocks until stop() is called."""
    global _send_queue, _stop_event
    _send_queue = asyncio.Queue(maxsize=2048)
    _stop_event = asyncio.Event()

    uri = (
        f"{config.WS_BASE_URL}/ws/agents/sessions/{session_id}"
        f"/students/{student_id}?token={token}"
    )
    await _connection_loop(uri)


async def stop():
    """Signal graceful shutdown."""
    if _stop_event:
        _stop_event.set()


async def send(event: dict):
    """Enqueue an outbound message (dict → JSON).

    If the queue is full the oldest item is dropped to avoid memory pressure.
    """
    if _send_queue is None:
        return
    if _send_queue.full():
        try:
            _send_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await _send_queue.put(event)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

async def _connection_loop(uri: str):
    """Reconnect loop with exponential back-off + jitter."""
    global _ws
    backoff = config.RECONNECT_BASE

    while not _stop_event.is_set():
        try:
            log.info("Connecting to %s …", uri)
            async with websockets.connect(
                uri,
                compression="deflate",
                ping_interval=config.HEARTBEAT_INTERVAL,
                ping_timeout=config.HEARTBEAT_INTERVAL * 3,
                close_timeout=5,
                max_size=2**20,   # 1 MiB
            ) as ws:
                _ws = ws
                backoff = config.RECONNECT_BASE
                log.info("WebSocket connected")

                # Wait for ack from server
                try:
                    ack_raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    ack = json.loads(ack_raw)
                    _apply_server_config(ack)
                    log.info("Server ack received: %s", ack)
                except asyncio.TimeoutError:
                    log.warning("No ack received within 10 s — using defaults")

                # Run reader + writer concurrently
                reader_task = asyncio.create_task(_reader(ws))
                writer_task = asyncio.create_task(_writer(ws))
                stop_task = asyncio.create_task(_stop_event.wait())

                done, pending = await asyncio.wait(
                    [reader_task, writer_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()

                if _stop_event.is_set():
                    log.info("Shutdown requested — closing WS")
                    return

        except (ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
            log.warning("Connection lost (%s). Retrying in %.1f s …", exc, backoff)

        if _stop_event.is_set():
            return

        await asyncio.sleep(backoff + random.uniform(0, 0.5))
        backoff = min(backoff * 2, config.RECONNECT_MAX)


async def _reader(ws):
    """Read server → agent messages."""
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Non-JSON from server: %s", raw[:200])
            continue

        event_type = msg.get("type")
        if event_type == "session_ended":
            log.info("Session ended signal from server — shutting down")
            _stop_event.set()
            return
        elif event_type == "config_update":
            _apply_server_config(msg)
        else:
            log.debug("Server message: %s", msg)


async def _writer(ws):
    """Drain the outbound queue → WebSocket."""
    while True:
        event = await _send_queue.get()
        try:
            payload = json.dumps(event)
            await ws.send(payload)
        except ConnectionClosed:
            # Re-enqueue so reconnect loop can retry
            await _send_queue.put(event)
            raise


def _apply_server_config(msg: dict):
    """Override local intervals from server ack / config_update."""
    data = msg.get("data") or msg
    if "snapshotIntervalSec" in data:
        config.SNAPSHOT_INTERVAL = int(data["snapshotIntervalSec"])
    if "deltaIntervalSec" in data:
        config.DELTA_INTERVAL = int(data["deltaIntervalSec"])
    if "heartbeatIntervalSec" in data:
        config.HEARTBEAT_INTERVAL = int(data["heartbeatIntervalSec"])
