"""process_monitor.py — Track running processes via psutil.

Emits three event types:
  • processes_snapshot  – full list every SNAPSHOT_INTERVAL seconds
  • process_new         – when a new PID appears between deltas
  • process_update      – when CPU% or mem changes beyond threshold
  • process_end         – when a previously-seen PID disappears

Processes are now classified before emission:
  - SAFE       → filtered out (low priority)
  - SUSPICIOUS → risk_level = "medium", category = "suspicious"
  - DANGEROUS  → risk_level = "high",   category = "dangerous"
  - Unknown    → included only if CPU > threshold or unknown binary
"""

import asyncio
import logging
import time

import psutil

from .. import config

log = logging.getLogger("lab_guardian.monitor.process")

# Internal state — keyed by PID
_prev_snapshot: dict[int, dict] = {}

# ---------------------------------------------------------------------------
# Process classification
# ---------------------------------------------------------------------------

SAFE_PROCESSES = {
    "chrome", "firefox", "code", "explorer", "nautilus", "xfce4-panel",
    "gnome-shell", "systemd", "svchost", "csrss", "dwm", "conhost",
    "winlogon", "lsass", "services", "smss", "wininit", "taskhost",
    "spoolsv", "searchindexer", "runtimebroker", "shellexperiencehost",
    "sihost", "ctfmon", "fontdrvhost", "dllhost",
}

SUSPICIOUS_PROCESSES = {
    "anydesk", "teamviewer", "zoom", "discord", "skype", "telegram",
    "slack", "microsoft teams", "teams", "rustdesk", "parsec",
    "vnc", "vncserver", "vncviewer", "remotedesktop",
}

DANGEROUS_PROCESSES = {
    "bash", "terminal", "python", "python3", "powershell", "cmd",
    "sh", "zsh", "fish", "ksh", "csh", "node", "ruby", "perl",
    "wsl", "mintty", "xterm", "konsole", "gnome-terminal",
    "alacritty", "kitty", "iterm2", "hyper", "terminator",
}

# Human-readable labels for known process names
PROCESS_LABELS = {
    "anydesk": "Remote Access Tool",
    "teamviewer": "Remote Access Tool",
    "zoom": "Video Conferencing App",
    "discord": "Communication App",
    "skype": "Communication App",
    "telegram": "Messaging App",
    "slack": "Communication App",
    "teams": "Video Conferencing App",
    "bash": "Terminal Opened",
    "terminal": "Terminal Opened",
    "python": "Python Interpreter",
    "python3": "Python Interpreter",
    "powershell": "PowerShell Terminal",
    "cmd": "Command Prompt",
    "sh": "Shell Opened",
    "zsh": "Shell Opened",
    "node": "Node.js Runtime",
    "ruby": "Ruby Interpreter",
    "perl": "Perl Interpreter",
    "wsl": "Linux Subsystem",
}

# CPU threshold for including unknown processes (percent)
UNKNOWN_CPU_THRESHOLD = 5.0


def _classify_process(proc_info: dict) -> dict | None:
    """Classify a process and enrich with risk_level, category, label.

    Returns None if the process should be filtered out (safe / low priority).
    Returns the enriched dict otherwise.
    """
    name_lower = (proc_info.get("name") or "").lower()

    # Safe processes → skip
    if name_lower in SAFE_PROCESSES:
        return None

    if name_lower in DANGEROUS_PROCESSES:
        proc_info["risk_level"] = "high"
        proc_info["category"] = "dangerous"
        proc_info["label"] = PROCESS_LABELS.get(name_lower, "Dangerous Process")
        return proc_info

    if name_lower in SUSPICIOUS_PROCESSES:
        proc_info["risk_level"] = "medium"
        proc_info["category"] = "suspicious"
        proc_info["label"] = PROCESS_LABELS.get(name_lower, "Suspicious Application")
        return proc_info

    # Unknown binary — include only if CPU > threshold
    cpu = proc_info.get("cpu", 0.0)
    if cpu >= UNKNOWN_CPU_THRESHOLD:
        proc_info["risk_level"] = "low"
        proc_info["category"] = "unknown"
        proc_info["label"] = "Unknown Process (High CPU)"
        return proc_info

    # Low CPU unknown process → skip
    return None


def _make_meta(proc_info: dict, msg_override: str | None = None) -> dict:
    """Build standardised meta block."""
    return {
        "risk_level": proc_info.get("risk_level", "low"),
        "category": proc_info.get("category", "process"),
        "message": msg_override or proc_info.get("label", "Process event"),
    }


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _take_snapshot() -> dict[int, dict]:
    """Return dict of {pid: info} for all running user processes."""
    procs: dict[int, dict] = {}
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info", "status", "create_time"]):
        try:
            info = proc.info
            procs[info["pid"]] = {
                "pid": info["pid"],
                "name": info["name"] or "unknown",
                "user": info["username"] or "",
                "cpu": round(info["cpu_percent"] or 0.0, 2),
                "memory": round((info["memory_info"].rss if info["memory_info"] else 0) / (1024 * 1024), 2),
                "status": info["status"] or "unknown",
                "started_at": info["create_time"],
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs


def _filter_and_classify(snapshot: dict[int, dict]) -> list[dict]:
    """Apply classification filter and return only relevant processes."""
    result = []
    for proc in snapshot.values():
        classified = _classify_process(dict(proc))  # copy so we don't mutate state
        if classified is not None:
            result.append(classified)
    return result


def _diff(prev: dict[int, dict], curr: dict[int, dict]) -> list[dict]:
    """Compute delta events between two snapshots (with classification)."""
    events: list[dict] = []

    new_pids = set(curr) - set(prev)
    gone_pids = set(prev) - set(curr)

    for pid in new_pids:
        classified = _classify_process(dict(curr[pid]))
        if classified is not None:
            events.append({
                "type": "process_new",
                "data": classified,
                "meta": _make_meta(classified, f"{classified.get('label', classified['name'])} started"),
            })

    for pid in gone_pids:
        prev_proc = prev[pid]
        classified = _classify_process(dict(prev_proc))
        if classified is not None:
            events.append({
                "type": "process_end",
                "data": {"pid": pid, "name": prev_proc.get("name", "")},
                "meta": _make_meta(classified, f"{classified.get('label', prev_proc['name'])} ended"),
            })

    for pid in set(curr) & set(prev):
        c, p = curr[pid], prev[pid]
        cpu_delta = abs(c["cpu"] - p["cpu"])
        mem_delta = abs(c["memory"] - p["memory"])
        if cpu_delta >= config.CPU_CHANGE_THRESHOLD or mem_delta >= config.MEM_CHANGE_THRESHOLD:
            classified = _classify_process(dict(c))
            if classified is not None:
                events.append({
                    "type": "process_update",
                    "data": classified,
                    "meta": _make_meta(classified),
                })

    return events


async def run(send_fn):
    """Long-running coroutine that monitors processes.

    *send_fn* is an ``async def send(event: dict)`` callback used to
    dispatch events to the WebSocket layer.
    """
    global _prev_snapshot

    log.info("Process monitor started")
    last_snapshot_ts = 0.0

    while True:
        now = time.monotonic()
        curr = _take_snapshot()

        # Full snapshot on first run or every SNAPSHOT_INTERVAL
        if now - last_snapshot_ts >= config.SNAPSHOT_INTERVAL or not _prev_snapshot:
            filtered = _filter_and_classify(curr)

            high_count = sum(1 for p in filtered if p.get("risk_level") == "high")
            med_count = sum(1 for p in filtered if p.get("risk_level") == "medium")
            overall_risk = "high" if high_count > 0 else ("medium" if med_count > 0 else "low")

            await send_fn({
                "type": "process_snapshot",
                "data": filtered,
                "ts": time.time(),
                "meta": {
                    "risk_level": overall_risk,
                    "category": "process",
                    "message": f"{len(filtered)} notable process(es) running",
                },
            })
            last_snapshot_ts = now
        else:
            # Delta events
            deltas = _diff(_prev_snapshot, curr)
            for evt in deltas:
                evt["ts"] = time.time()
                await send_fn(evt)

        _prev_snapshot = curr
        await asyncio.sleep(config.DELTA_INTERVAL)
