"""process_monitor.py — Track running processes via psutil.

Emits three event types:
  • process_snapshot  – full list every SNAPSHOT_INTERVAL seconds
  • process_new       – when a new PID appears between deltas
  • process_update    – when CPU% or mem changes beyond threshold
  • process_end       – when a previously-seen PID disappears

Processes are classified before emission:
  - SAFE       → filtered out (low priority)
  - SUSPICIOUS → risk_level = "medium", category = "suspicious"
  - DANGEROUS  → risk_level = "high",   category = "dangerous"
  - INCOGNITO  → risk_level = "high",   category = "incognito"
  - Unknown    → included only if CPU > threshold or unknown binary

Changes in this version
-----------------------
1. Browser child processes (renderer, GPU, utility, etc.) are now skipped so
   only the main browser process is classified — this also fixes the case where
   --incognito appeared on dozens of renderer PIDs.
2. _get_proc_obj() eliminates the race between snapshot-build and proc_map-build
   by attempting a fresh psutil.Process(pid) lookup when the cached object is dead.
3. Firefox private-window detection now checks the sessionstore recovery file
   (requires optional 'lz4' package; degrades gracefully when absent).
4. _is_browser_child_process() skips renderer/gpu/utility/extension child procs.
"""

import asyncio
import glob
import json
import logging
import os
import time

import psutil

from .. import config

log = logging.getLogger("lab_guardian.monitor.process")

# Internal state — keyed by PID
_prev_snapshot: dict[int, dict] = {}

# ---------------------------------------------------------------------------
# Browser child-process detection
# ---------------------------------------------------------------------------

# Chromium-family browsers spawn child processes with --type=<value>.
# These must NOT be classified individually — only the main browser process matters.
_BROWSER_CHILD_TYPES = {
    "renderer", "gpu-process", "utility", "extension",
    "crashpad-handler", "zygote", "ppapi", "ppapi-broker",
    "nacl-loader", "sandbox-ipc",
}


def _is_browser_child_process(cmdline: list) -> bool:
    """Return True if this is a Chromium-family child/helper process.

    Child processes always carry a --type=<something> flag.  The main browser
    process either has no --type flag or has --type=browser.
    """
    if not cmdline:
        return False
    cmdline_str = " ".join(cmdline)
    for child_type in _BROWSER_CHILD_TYPES:
        if f"--type={child_type}" in cmdline_str:
            return True
    return False


# ---------------------------------------------------------------------------
# Process classification tables
# ---------------------------------------------------------------------------

SAFE_PROCESSES = {
    # System processes (Linux)
    "systemd", "systemd-journal", "systemd-udevd", "systemd-logind", "systemd-resolved",
    "systemd-timesyn", "dbus-daemon", "accounts-daemon", "udisksd", "polkitd",
    "networkmanager", "wpa_supplicant", "bluetoothd", "cron", "atd", "sshd",
    "rsyslogd", "cupsd", "avahi-daemon", "thermald", "irqbalance",
    "modemmanager", "switcheroo-control", "gdm3", "lightdm", "sddm",

    # System processes (Windows)
    "svchost", "csrss", "dwm", "winlogon", "lsass", "services", "smss",
    "wininit", "taskhost", "taskhostw", "spoolsv", "searchindexer",
    "searchprotocolhost", "searchfilterhost", "runtimebroker",
    "shellexperiencehost", "sihost", "ctfmon", "fontdrvhost", "dllhost",
    "lsaiso", "wmiprvse", "conhost", "compattelrunner", "moone",

    # File managers / DE
    "explorer", "nautilus", "dolphin", "thunar", "xfce4-panel", "gnome-shell",
}

SUSPICIOUS_PROCESSES = {
    # Web Browsers
    "chrome", "google-chrome", "chromium", "chromium-browser",
    "firefox", "firefox-esr",
    "msedge", "microsoft-edge",
    "brave", "brave-browser",
    "opera", "opera-browser",
    "vivaldi", "vivaldi-stable",
    "safari", "epiphany", "midori",

    # Communication apps
    "zoom", "microsoft teams", "teams", "skype",
    "discord", "telegram", "whatsapp", "signal",
    "slack", "webex", "gotomeeting",

    # Terminal emulators (suspicious but not always dangerous)
    "terminal", "iterm", "iterm2", "wsl", "wslhost",

    # IDEs and Code Editors
    "code", "code-insiders", "code-oss",
    "sublime_text", "atom", "gedit", "nano", "vim", "vi",

    # Development tools
    "java", "javac", "gcc", "g++", "clang", "clangd",
    "docker", "docker-compose", "containerd",
}

DANGEROUS_PROCESSES = {
    # Remote access tools
    "anydesk", "teamviewer", "rustdesk", "parsec",
    "vnc", "vncserver", "vncviewer", "remotedesktop",

    # Shells
    "bash", "zsh", "fish", "ksh", "csh", "sh",
    "powershell", "pwsh", "cmd", "command",
    "mintty", "xterm", "konsole", "gnome-terminal",
    "alacritty", "kitty", "iterm2", "hyper", "terminator",
    "wt", "windowsterminal",
}

PROCESS_LABELS = {
    "anydesk": "AnyDesk Remote Access",
    "teamviewer": "TeamViewer Remote Access",
    "zoom": "Zoom Video Conferencing",
    "discord": "Discord Chat Application",
    "skype": "Skype Communication",
    "telegram": "Telegram Messenger",
    "slack": "Slack Communication",
    "teams": "Microsoft Teams",
    "bash": "Bash Shell",
    "terminal": "Terminal Emulator",
    "python": "Python Interpreter",
    "python3": "Python 3 Interpreter",
    "powershell": "PowerShell Terminal",
    "pwsh": "PowerShell 7+",
    "cmd": "Command Prompt",
    "command": "Windows Command Processor",
    "sh": "Shell",
    "zsh": "Z Shell",
    "fish": "Fish Shell",
    "ksh": "Korn Shell",
    "csh": "C Shell",
    "node": "Node.js Runtime",
    "nodejs": "Node.js Runtime",
    "ruby": "Ruby Interpreter",
    "perl": "Perl Interpreter",
    "php": "PHP Interpreter",
    "wsl": "Windows Subsystem for Linux",
    "wslhost": "WSL Host Process",
    "mintty": "MinTTY Terminal",
    "xterm": "X Terminal",
    "konsole": "KDE Console",
    "gnome-terminal": "GNOME Terminal",
    "alacritty": "Alacritty Terminal",
    "kitty": "Kitty Terminal",
    "iterm": "iTerm Terminal",
    "iterm2": "iTerm2 Terminal",
    "hyper": "Hyper Terminal",
    "terminator": "Terminator Terminal",
    "wt": "Windows Terminal",
    "windowsterminal": "Windows Terminal",
    "rustdesk": "RustDesk Remote Access",
    "parsec": "Parsec Remote Desktop",
    "vnc": "VNC Remote Access",
    "vncserver": "VNC Server",
    "vncviewer": "VNC Viewer",
    "remotedesktop": "Remote Desktop",
    "whatsapp": "WhatsApp Messenger",
    "signal": "Signal Messenger",
    "webex": "Cisco WebEx",
    "gotomeeting": "GoToMeeting",
    "deno": "Deno Runtime",
    "bun": "Bun Runtime",
}

# CPU threshold for including unknown processes (percent)
UNKNOWN_CPU_THRESHOLD = 5.0

# Incognito/Private browsing indicators in command line
INCOGNITO_FLAGS = {
    "--incognito", "-incognito",          # Chrome / Chromium
    "--private", "-private",              # Firefox (CLI launch)
    "--private-window", "-private-window",  # Firefox (CLI launch, newer)
    "--inprivate", "-inprivate",          # Edge
    "--private-browsing",                 # Safari
}

# ---------------------------------------------------------------------------
# Process object helper — eliminates race between snapshot and proc_map build
# ---------------------------------------------------------------------------

def _get_proc_obj(pid: int, proc_map: dict) -> "psutil.Process | None":
    """Return a live psutil.Process for *pid*, using *proc_map* as a cache.

    The snapshot dict and the proc_map are built in two separate
    psutil.process_iter() passes.  Between those two passes a process may have
    exited, leaving a dead object in proc_map.  This function tests liveness
    and falls back to a fresh psutil.Process(pid) lookup before giving up.
    """
    cached = proc_map.get(pid) if proc_map else None
    if cached is not None:
        try:
            cached.cmdline()   # cheap liveness probe
            return cached
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass
    # Fallback: fresh lookup
    try:
        return psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return None


# ---------------------------------------------------------------------------
# Incognito / private-window detection
# ---------------------------------------------------------------------------

def _check_incognito(proc) -> bool:
    """Return True if the browser process is running in incognito/private mode.

    Only examines the MAIN browser process.  Child processes (renderer, GPU,
    utility …) carry the same --incognito flag but should not be flagged
    individually — _is_browser_child_process() filters them out earlier in
    _classify_process().
    """
    try:
        cmdline = proc.cmdline()
        if not cmdline:
            return False

        # Skip browser child/helper processes
        if _is_browser_child_process(cmdline):
            return False

        cmdline_str = " ".join(cmdline).lower()
        for flag in INCOGNITO_FLAGS:
            if flag in cmdline_str:
                return True
        return False
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return False


def _check_firefox_private_window() -> bool:
    """Detect a live Firefox private window via the sessionstore recovery file.

    When the user opens a private window from inside an already-running Firefox,
    the --private-window flag only appears on a short-lived helper process that
    exits immediately — the main Firefox process never shows it in cmdline.

    The only reliable OS-level signal is Firefox's own sessionstore file:
      ~/.mozilla/firefox/<profile>/sessionstore-backups/recovery.jsonlz4

    This file uses Mozilla's custom LZ4 framing (magic "mozLz40\\0" + 4-byte
    uncompressed length + raw LZ4 block).  We decompress it with the optional
    lz4 package (lz4.block.decompress with unframed=False after stripping the
    8-byte Mozilla header).

    Returns True  — private window confirmed.
    Returns False — no private window, lz4 unavailable, or any error.
    Fails silently in all error cases.
    """
    profile_patterns = [
        os.path.expanduser("~/.mozilla/firefox/*/sessionstore-backups/recovery.jsonlz4"),
        os.path.expanduser("~/snap/firefox/common/.mozilla/firefox/*/sessionstore-backups/recovery.jsonlz4"),
        os.path.expanduser("~/snap/firefox/current/.mozilla/firefox/*/sessionstore-backups/recovery.jsonlz4"),
        os.path.expanduser("~/AppData/Roaming/Mozilla/Firefox/Profiles/*/sessionstore-backups/recovery.jsonlz4"),
    ]

    try:
        import lz4.block as _lz4_block
    except ImportError:
        # lz4 not installed — degraded mode, cannot check sessionstore
        log.debug("lz4 not available; Firefox sessionstore private-window check skipped")
        return False

    for pattern in profile_patterns:
        for path in glob.glob(pattern):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()

                # Mozilla LZ4 framing: 8-byte magic + 4-byte uncompressed length
                # (little-endian) + raw LZ4 block data.
                MAGIC = b"mozLz40\x00"
                if not raw.startswith(MAGIC):
                    continue

                # The 4 bytes after the magic are the uncompressed size (uint32 LE).
                import struct
                uncompressed_size = struct.unpack_from("<I", raw, len(MAGIC))[0]
                compressed_payload = raw[len(MAGIC) + 4:]

                data = _lz4_block.decompress(
                    compressed_payload,
                    uncompressed_size=uncompressed_size,
                )
                state = json.loads(data.decode("utf-8", errors="replace"))

                for window in state.get("windows", []):
                    if window.get("isPrivate"):
                        log.info("Firefox private window detected via sessionstore: %s", path)
                        return True

            except Exception as exc:
                log.debug("sessionstore check failed for %s: %s", path, exc)
                continue

    return False


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify_process(proc_info: dict, proc_obj=None) -> dict | None:
    """Classify a process and enrich with risk_level, category, label.

    Returns None  → process should be filtered out (safe / low priority).
    Returns dict  → enriched proc_info ready for emission.
    """
    name_lower = (proc_info.get("name") or "").lower()

    # ── Step 1: skip browser child/helper processes entirely ─────────────────
    # Chromium spawns dozens of renderer/GPU/utility child processes that all
    # appear under the same binary name.  Classifying each one independently
    # would flood the process list and cause duplicate incognito alerts.
    if proc_obj is not None:
        try:
            cmdline = proc_obj.cmdline()
            if _is_browser_child_process(cmdline):
                return None
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass

    # ── Step 2: incognito / private-window detection ─────────────────────────
    is_incognito = False
    if proc_obj is not None:
        is_incognito = _check_incognito(proc_obj)

    # Firefox: also check sessionstore for private windows opened from the menu
    if not is_incognito and name_lower in {"firefox", "firefox-esr"}:
        is_incognito = _check_firefox_private_window()

    if is_incognito:
        proc_info["risk_level"] = "high"
        proc_info["category"] = "incognito"
        proc_info["label"] = f"{proc_info.get('name', 'Browser')} (Incognito/Private Mode)"
        proc_info["is_incognito"] = True
        return proc_info

    # ── Step 3: standard classification ──────────────────────────────────────

    # Safe processes → skip
    if name_lower in SAFE_PROCESSES:
        return None

    if name_lower in DANGEROUS_PROCESSES:
        proc_info["risk_level"] = "high"
        proc_info["category"] = "dangerous"
        proc_info["label"] = PROCESS_LABELS.get(name_lower, proc_info.get("name", "Unknown Process"))
        return proc_info

    if name_lower in SUSPICIOUS_PROCESSES:
        proc_info["risk_level"] = "medium"
        proc_info["category"] = "suspicious"
        proc_info["label"] = PROCESS_LABELS.get(name_lower, proc_info.get("name", "Unknown Process"))
        return proc_info

    # Unknown binary — include only if CPU > threshold
    cpu = proc_info.get("cpu", 0.0)
    if cpu >= UNKNOWN_CPU_THRESHOLD:
        proc_info["risk_level"] = "low"
        proc_info["category"] = "unknown"
        proc_info["label"] = proc_info.get("name", "Unknown Process")
        return proc_info

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

def _take_snapshot() -> tuple[dict[int, dict], dict[int, "psutil.Process"]]:
    """Return (pid_info_dict, pid_proc_obj_dict) for all running user processes.

    Both dicts are built in a SINGLE psutil.process_iter() pass to eliminate
    the race condition that previously existed when the two dicts were built in
    separate passes.

    Filters out:
    - System processes (root/SYSTEM/NETWORK SERVICE)
    - Processes with very low CPU and memory usage
    """
    import getpass

    procs: dict[int, dict] = {}
    proc_map: dict[int, psutil.Process] = {}

    current_user = None
    try:
        current_user = getpass.getuser()
    except Exception:
        pass

    attrs = ["pid", "name", "username", "cpu_percent", "memory_info", "status", "create_time"]

    for proc in psutil.process_iter(attrs):
        try:
            info = proc.info

            if not info.get("username"):
                continue

            username = info["username"] or ""

            if username.lower() in ["root", "system", "network service", "local service"]:
                if current_user and current_user.lower() != "root":
                    continue

            cpu = round(info["cpu_percent"] or 0.0, 2)
            memory_mb = round(
                (info["memory_info"].rss if info["memory_info"] else 0) / (1024 * 1024), 2
            )

            name_lower = (info["name"] or "").lower()
            is_notable = (
                cpu > 0.5
                or memory_mb > 30.0
                or name_lower in DANGEROUS_PROCESSES
                or name_lower in SUSPICIOUS_PROCESSES
            )

            if not is_notable:
                continue

            pid = info["pid"]
            procs[pid] = {
                "pid": pid,
                "name": info["name"] or "unknown",
                "user": username,
                "cpu": cpu,
                "memory": memory_mb,
                "status": info["status"] or "unknown",
                "started_at": info["create_time"],
            }
            # Store the live process object in the same pass — no race.
            proc_map[pid] = proc

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return procs, proc_map


def _filter_and_classify(
    snapshot: dict[int, dict],
    proc_map: dict[int, "psutil.Process"] | None = None,
) -> list[dict]:
    """Apply classification filter and return only relevant processes."""
    result = []
    for pid, proc_data in snapshot.items():
        proc_obj = _get_proc_obj(pid, proc_map)
        classified = _classify_process(dict(proc_data), proc_obj)
        if classified is not None:
            result.append(classified)
    return result


def _diff(
    prev: dict[int, dict],
    curr: dict[int, dict],
    prev_map: dict | None = None,
    curr_map: dict | None = None,
) -> list[dict]:
    """Compute delta events between two snapshots (with classification)."""
    events: list[dict] = []

    new_pids = set(curr) - set(prev)
    gone_pids = set(prev) - set(curr)

    for pid in new_pids:
        proc_obj = _get_proc_obj(pid, curr_map)
        classified = _classify_process(dict(curr[pid]), proc_obj)
        if classified is not None:
            events.append({
                "type": "process_new",
                "data": classified,
                "meta": _make_meta(classified, f"{classified.get('label', classified['name'])} started"),
            })

    for pid in gone_pids:
        prev_proc = prev[pid]
        # Ended processes are already gone — proc_obj will be None; that is fine.
        proc_obj = _get_proc_obj(pid, prev_map)
        classified = _classify_process(dict(prev_proc), proc_obj)
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
            proc_obj = _get_proc_obj(pid, curr_map)
            classified = _classify_process(dict(c), proc_obj)
            if classified is not None:
                events.append({
                    "type": "process_update",
                    "data": classified,
                    "meta": _make_meta(classified),
                })

    return events


# ---------------------------------------------------------------------------
# Main monitor coroutine
# ---------------------------------------------------------------------------

async def run(send_fn):
    """Long-running coroutine that monitors processes.

    *send_fn* is an ``async def send(event: dict)`` callback used to
    dispatch events to the local DB layer.
    """
    global _prev_snapshot

    log.info("Process monitor started")
    last_snapshot_ts = 0.0
    prev_proc_map: dict[int, psutil.Process] = {}

    while True:
        now = time.monotonic()

        # _take_snapshot() now builds BOTH the data dict and the proc_map in a
        # single psutil.process_iter() pass — eliminates the previous race.
        curr, curr_proc_map = _take_snapshot()

        # Full snapshot on first run or every SNAPSHOT_INTERVAL
        if now - last_snapshot_ts >= config.SNAPSHOT_INTERVAL or not _prev_snapshot:
            filtered = _filter_and_classify(curr, curr_proc_map)

            high_count = sum(1 for p in filtered if p.get("risk_level") == "high")
            med_count  = sum(1 for p in filtered if p.get("risk_level") == "medium")
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
            # Delta events — use prev_proc_map for gone PIDs, curr_proc_map for new ones
            deltas = _diff(_prev_snapshot, curr, prev_proc_map, curr_proc_map)
            for evt in deltas:
                evt["ts"] = time.time()
                await send_fn(evt)

        _prev_snapshot = curr
        prev_proc_map = curr_proc_map
        await asyncio.sleep(config.DELTA_INTERVAL)