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
import os
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
    vendor = device_info.get("metadata", {}).get("vendor", "")
    model = device_info.get("metadata", {}).get("model", "")
    
    # Build a readable name from vendor/model if available
    if vendor or model:
        readable = f"{vendor} {model}".strip()
        if not readable:
            readable = "USB Storage Device"
    else:
        readable = "USB Storage Device"
    
    if dev_type == "usb":
        device_info["readable_name"] = readable
        device_info["risk_level"] = "high"
        device_info["message"] = f"{readable} connected"
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


def _get_usb_vendor_model(device_path: str) -> tuple[str, str]:
    """Extract vendor and model from sysfs for a USB device.
    
    Args:
        device_path: Device path like /dev/sdb
        
    Returns:
        Tuple of (vendor, model) strings
    """
    vendor = ""
    model = ""
    
    try:
        # Extract device name (e.g., sdb from /dev/sdb)
        dev_name = device_path.split("/")[-1] if device_path else ""
        if not dev_name:
            return vendor, model
        
        # Try to read from sysfs
        # Path: /sys/block/sdb/device/vendor
        vendor_path = f"/sys/block/{dev_name}/device/vendor"
        model_path = f"/sys/block/{dev_name}/device/model"
        
        if os.path.exists(vendor_path):
            with open(vendor_path, 'r') as f:
                vendor = f.read().strip()
        
        if os.path.exists(model_path):
            with open(model_path, 'r') as f:
                model = f.read().strip()
        
        # Clean up vendor/model strings
        vendor = vendor.replace('"', '').strip()
        model = model.replace('"', '').strip()
        
        # Map common vendor IDs to brand names
        vendor_map = {
            '0x0781': 'SanDisk',
            '0x090c': 'Silicon Motion',
            '0x1307': 'Transcend',
            '0x0951': 'Kingston',
            '0x04e8': 'Samsung',
            '0x0480': 'Toshiba',
            '0x0718': 'Imation',
            '0x058f': 'Alcor Micro',
            '0x0930': 'Toshiba',
            '0x0bda': 'Realtek',
            '0x125f': 'A-DATA',
            '0x1f75': 'InnoDisk',
            '0x0cf2': 'ENE Technology',
            '0x05dc': 'Lexar',
            '0x2006': 'ADATA',
            '0x14cd': 'Super Top',
            '0x0409': 'NEC',
            '0x067b': 'Prolific Technology',
            '0x1b1c': 'Corsair',
            '0x1058': 'Western Digital',
            '0x0bc2': 'Seagate',
            '0x045b': 'Hitachi',
            '0x03f0': 'HP',
            '0x046d': 'Logitech',
            '0x04b3': 'IBM',
            '0x04f2': 'Chicony',
            '0x062a': 'MosArt Semiconductor',
            '0x0764': 'Cyber Power',
            '0x0781': 'SanDisk',
            '0x08bb': 'Texas Instruments',
            '0x0923': 'IC Media',
            '0x0a5c': 'Broadcom',
            '0x0b95': 'ASIX Electronics',
            '0x0c0b': 'VIA Technologies',
            '0x1043': 'ASUS',
            '0x10d6': 'Actions Semiconductor',
            '0x13fe': 'Kingston',
            '0x14cd': 'Super Top',
            '0x1516': 'Compal Electronics',
            '0x152d': 'JMicron',
            '0x15d9': 'Trust',
            '0x17ef': 'Lenovo',
            '0x18a5': 'Verbatim',
            '0x1b1c': 'Corsair',
            '0x2109': 'VIA Labs',
            '0x2207': 'Rockchip',
            '0x24ae': 'Rapoo',
            '0x25a7': 'FAE',
            '0x2717': 'Xiaomi',
            '0x2940': 'OEM',
            '0x2cb7': 'FireFly',
            '0x3318': 'OEM',
        }
        
        # If vendor is a hex ID, try to map it
        if vendor.startswith('0x') and vendor.lower() in vendor_map:
            vendor = vendor_map[vendor.lower()]
        
    except Exception as e:
        log.debug(f"Failed to read USB vendor/model for {device_path}: {e}")
    
    return vendor, model


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _get_base_device(device_path: str) -> str:
    """Get the base device name from a partition path.
    
    Examples:
        /dev/sda1 -> /dev/sda
        /dev/sda -> /dev/sda
        /dev/mmcblk0p1 -> /dev/mmcblk0
        /dev/nvme0n1p1 -> /dev/nvme0n1
    """
    import re
    dev = device_path
    
    # Handle NVMe devices: /dev/nvme0n1p1 -> /dev/nvme0n1
    if 'nvme' in dev:
        # Match pattern like nvme0n1p1 -> keep nvme0n1
        match = re.match(r'(/dev/nvme\d+n\d+)', dev)
        if match:
            return match.group(1)
        return dev
    
    # Handle MMC/SD cards: /dev/mmcblk0p1 -> /dev/mmcblk0
    if 'mmcblk' in dev:
        match = re.match(r'(/dev/mmcblk\d+)', dev)
        if match:
            return match.group(1)
        return dev
    
    # Handle standard SCSI/SATA: /dev/sda1 -> /dev/sda, /dev/sda -> /dev/sda
    # Remove trailing digits
    base = re.sub(r'\d+$', '', dev)
    return base if base else device_path


def _collect_devices() -> dict[str, dict]:
    """Return dict keyed by base device path, with fields matching backend schema.
    
    Only collects USB storage devices (removable drives).
    Filters out internal drives, network drives, and virtual drives.
    Groups multiple partitions of the same physical device into one entry.
    """
    devices: dict[str, dict] = {}
    for part in psutil.disk_partitions(all=False):
        # Skip non-removable drives
        opts = part.opts.lower() if part.opts else ""
        
        # Only include removable/USB drives
        # Check for common USB indicators
        is_usb = (
            "removable" in opts or 
            part.device.startswith("/dev/sd") or  # SCSI/SATA USB drives
            part.device.startswith("/dev/mmcblk") or  # SD cards
            part.fstype.lower() in ("vfat", "exfat", "ntfs", "fuseblk")  # Common USB filesystems
        )
        
        # Skip if not USB
        if not is_usb:
            continue
            
        # Additional check: skip if it looks like an internal drive
        if part.mountpoint in ["/", "/boot", "/home", "/var", "/usr", "/tmp"]:
            continue
        
        # Get base device name (group partitions together)
        base_device = _get_base_device(part.device)
        
        # Skip if we already recorded this base device
        if base_device in devices:
            continue
            
        usage = None
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            pass

        dev_info = {
            "id": base_device,
            "name": f"{base_device} ({part.mountpoint})",
            "type": "usb",
            "metadata": {
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024 ** 3), 2) if usage else None,
                "used_gb": round(usage.used / (1024 ** 3), 2) if usage else None,
            },
        }
        
        # Try to get USB vendor/model information
        vendor, model = _get_usb_vendor_model(base_device)
        if vendor:
            dev_info["metadata"]["vendor"] = vendor
        if model:
            dev_info["metadata"]["model"] = model
        
        # Enrich with classification
        _classify_device(dev_info)
        devices[base_device] = dev_info
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
            # Only send USB devices (external array will be empty)
            snapshot_data = {
                "usb": all_devs,
                "external": [],
            }
            await send_fn({
                "type": "devices_snapshot",
                "data": snapshot_data,
                "ts": time.time(),
                "meta": {
                    "risk_level": "high" if snapshot_data["usb"] else "low",
                    "category": "device",
                    "message": f"{len(all_devs)} USB device(s) connected",
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
