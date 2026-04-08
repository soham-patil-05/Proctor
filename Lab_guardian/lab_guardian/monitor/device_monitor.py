"""device_monitor.py — Track connected USB / block devices.

Uses pyudev for event-driven detection on Linux; falls back to polling
`/sys/block` or `psutil.disk_partitions()` on other platforms.

Emits:
  • devices_snapshot    – full device list every SNAPSHOT_INTERVAL
  • device_connected    – new device detected
  • device_disconnected – device removed
"""

import asyncio
import logging
import platform
import time

import psutil

from .. import config

log = logging.getLogger("lab_guardian.monitor.device")

_prev_devices: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _classify_device(device_info: dict) -> dict:
    """Add human-readable classification fields to a device info dict.

    Enriches the device with:
      - readable_name  : examiner-friendly label
      - risk_level     : "high" | "medium" | "low"
      - message        : short human-readable description

    Original fields are preserved (non-destructive).
    """
    dev_type = device_info.get("type", "")
    if dev_type == "usb":
        device_info["readable_name"] = "USB Storage Device"
        device_info["risk_level"] = "high"
        device_info["message"] = "External USB device connected"
    else:
        device_info["readable_name"] = "External Storage"
        device_info["risk_level"] = "medium"
        device_info["message"] = "External storage detected"
    return device_info


def _make_meta(device_info: dict) -> dict:
    """Build the standardised `meta` block for an event envelope."""
    return {
        "risk_level": device_info.get("risk_level", "medium"),
        "category": device_info.get("type", "device"),
        "message": device_info.get("message", "Device event"),
    }


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _collect_devices() -> dict[str, dict]:
    """Return dict keyed by device path/name, with fields matching backend schema."""
    devices: dict[str, dict] = {}
    for part in psutil.disk_partitions(all=False):
        usage = None
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            pass
        # Classify: removable/loop → usb, otherwise → external
        opts = part.opts.lower() if part.opts else ""
        is_removable = "removable" in opts or part.device.startswith("/dev/sd")
        dev_type = "usb" if is_removable else "external"

        dev_info = {
            "id": part.device,
            "name": f"{part.device} ({part.mountpoint})",
            "type": dev_type,
            "metadata": {
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024 ** 3), 2) if usage else None,
                "used_gb": round(usage.used / (1024 ** 3), 2) if usage else None,
            },
        }
        # Enrich with classification
        _classify_device(dev_info)
        devices[part.device] = dev_info
    return devices


def _try_pyudev():
    """Try to import pyudev; returns (Context, Monitor) or None."""
    if platform.system() != "Linux":
        return None
    try:
        import pyudev  # noqa: E402
        ctx = pyudev.Context()
        mon = pyudev.Monitor.from_netlink(ctx)
        mon.filter_by(subsystem="usb")
        mon.start()
        return mon
    except Exception as exc:
        log.debug("pyudev unavailable (%s) — using polling", exc)
        return None


# ---------------------------------------------------------------------------
# Main coroutine
# ---------------------------------------------------------------------------

async def run(send_fn):
    """Long-running coroutine that monitors attached devices."""
    global _prev_devices

    log.info("Device monitor started")
    udev_monitor = _try_pyudev()
    last_snapshot_ts = 0.0

    while True:
        now = time.monotonic()
        curr = _collect_devices()

        # Full snapshot periodically
        if now - last_snapshot_ts >= config.SNAPSHOT_INTERVAL or not _prev_devices:
            all_devs = list(curr.values())
            snapshot_data = {
                "usb": [d for d in all_devs if d["type"] == "usb"],
                "external": [d for d in all_devs if d["type"] == "external"],
            }
            await send_fn({
                "type": "devices_snapshot",
                "data": snapshot_data,
                "ts": time.time(),
                "meta": {
                    "risk_level": "high" if snapshot_data["usb"] else "low",
                    "category": "device",
                    "message": f"{len(all_devs)} device(s) connected",
                },
            })
            last_snapshot_ts = now
        else:
            # Diff
            new_devs = set(curr) - set(_prev_devices)
            gone_devs = set(_prev_devices) - set(curr)
            for d in new_devs:
                dev_info = curr[d]
                await send_fn({
                    "type": "device_connected",
                    "data": dev_info,
                    "ts": time.time(),
                    "meta": _make_meta(dev_info),
                })
            for d in gone_devs:
                await send_fn({
                    "type": "device_disconnected",
                    "data": {"id": d},
                    "ts": time.time(),
                    "meta": {
                        "risk_level": "low",
                        "category": "device",
                        "message": "Device disconnected",
                    },
                })

        _prev_devices = curr

        # If pyudev is available, block briefly on udev events
        if udev_monitor is not None:
            await _poll_udev(udev_monitor, send_fn, timeout=config.DEVICE_POLL_INTERVAL)
        else:
            await asyncio.sleep(config.DEVICE_POLL_INTERVAL)


async def _poll_udev(monitor, send_fn, timeout: float):
    """Non-blocking check for udev events during the poll sleep."""
    loop = asyncio.get_event_loop()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        device = await loop.run_in_executor(None, lambda: monitor.poll(timeout=0.2))
        if device is None:
            continue
        action = device.action
        dev_id = device.device_node or device.sys_path
        if action == "add":
            dev_info = {
                "id": dev_id,
                "name": dev_id,
                "type": "usb",
                "metadata": {"subsystem": device.subsystem},
            }
            _classify_device(dev_info)
            await send_fn({
                "type": "device_connected",
                "data": dev_info,
                "ts": time.time(),
                "meta": _make_meta(dev_info),
            })
        elif action == "remove":
            await send_fn({
                "type": "device_disconnected",
                "data": {"id": dev_id},
                "ts": time.time(),
                "meta": {
                    "risk_level": "low",
                    "category": "device",
                    "message": "Device disconnected",
                },
            })
