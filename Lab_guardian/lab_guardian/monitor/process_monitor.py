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
    # System processes (Linux)
    "systemd", "systemd-journal", "systemd-udevd", "systemd-logind", "systemd-resolved",
    "systemd-timesyn", "systemd-timesyncd", "dbus-daemon", "accounts-daemon", "udisksd", "polkitd",
    "networkmanager", "wpa_supplicant", "bluetoothd", "cron", "crond", "atd", "sshd",
    "rsyslogd", "cupsd", "cups-browsed", "avahi-daemon", "thermald", "irqbalance",
    "modemmanager", "switcheroo-control", "gdm3", "lightdm", "sddm",
    "snapd", "snapd.service", "snapd.socket", "snapd.autoimport", "snapd.seeded",
    "snapd.core-fixup", "snapd.snap-repair", "snapd.refresh.timer",
    "pipewire", "pipewire-pulse", "wireplumber", "pulseaudio",
    "gnome-keyring-daemon", "gnome-keyring-ssh", "gnome-shell", "gnome-session-binary",
    "xwayland", "Xwayland", "Xorg", "X", "mutter", "kwin_x11", "kwin_wayland",
    "upowerd", "power-profiles-daemon", "packagekitd", "fwupd", "colord",
    "kernel", "kworker", "ksoftirqd", "migration", "rcu_sched", "rcu_bh",
    "jbd2", "ext4-rsv-conver", "loop", "loop0", "loop1", "loop2", "loop3",
    "snapfuse", "fuse", "gvfsd", "gvfsd-fuse", "gvfs-udisks2-volume-monitor",
    "vmware-vmblock-fuse", "vmware-user-suid-wrapper", "vmtoolsd",
    "update-notifier", "fwupd", "whoopsie", "apport", "apport-gtk",
    "agent​_loguploader", "agent​_xray", "amazon-ssm-agent", "snap.amazon-ssm-agent",
    "fwupd-refresh", "motd-news", "systemd-resolve", "systemd-networkd",
    "python3", "python",  # System python processes (usually background services)
    "agetty", "login", "bash", "zsh", "sh", "dash",  # Shells as system processes when run by system
    
    # System processes (Windows)
    "svchost", "csrss", "dwm", "winlogon", "lsass", "services", "smss",
    "wininit", "taskhost", "taskhostw", "spoolsv", "searchindexer",
    "searchprotocolhost", "searchfilterhost", "runtimebroker",
    "shellexperiencehost", "sihost", "ctfmon", "fontdrvhost", "dllhost",
    "lsaiso", "wmiprvse", "conhost", "compattelrunner", "moone",

    # File managers/DE (safe but we want to track browsers separately)
    "explorer", "nautilus", "dolphin", "thunar", "xfce4-panel", "gnome-shell",
}

SUSPICIOUS_PROCESSES = {
    # Web Browsers (important to track)
    "chrome", "google-chrome", "google-chrome-stable", "google-chrome-beta",
    "chromium", "chromium-browser",
    "firefox", "firefox-esr", "firefox-bin", "firefox-esr-bin",
    "firefox.real",  # Snap package wrapper
    "msedge", "microsoft-edge", "microsoft-edge-beta", "microsoft-edge-dev",
    "brave", "brave-browser",
    "opera", "opera-browser", "opera-beta", "opera-developer",
    "vivaldi", "vivaldi-stable", "vivaldi-snapshot",
    "safari", "epiphany", "midori",
    
    # Communication apps (can be used for cheating)
    "zoom", "microsoft teams", "teams", "skype", 
    "discord", "telegram", "whatsapp", "signal",
    "slack", "webex", "gotomeeting",
    
    # Terminal emulators (suspicious but not always dangerous)
    "terminal", "iterm", "iterm2", "wsl", "wslhost",
    
    # IDEs and Code Editors (important to track)
    "code", "code-insiders", "code-oss",  # VS Code
    "sublime_text", "atom", "gedit", "nano", "vim", "vi",
    
    # Development tools
    "java", "javac", "gcc", "g++", "clang", "clangd",
    "docker", "docker-compose", "containerd",
}

DANGEROUS_PROCESSES = {
    # Remote access tools (high risk during exams)
    "anydesk", "teamviewer", "rustdesk", "parsec",
    "vnc", "vncserver", "vncviewer", "remotedesktop",
    
    # Terminal processes (only flag if actively used)
    "bash", "zsh", "fish", "ksh", "csh", "sh",
    "powershell", "pwsh", "cmd", "command",
    "mintty", "xterm", "konsole", "gnome-terminal",
    "alacritty", "kitty", "iterm2", "hyper", "terminator",
    "wt", "windowsterminal",
}

# Human-readable labels for known process names
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
    # Chrome/Chromium
    "--incognito", "-incognito",
    # Firefox (various patterns including snap/firefox builds)
    "--private", "-private", "-private-window", "--private-window",
    "-foreground",  # Firefox private windows often have this pattern
    # Edge
    "--inprivate", "-inprivate",
    # Safari
    "--private-browsing",
}

# Firefox-specific private mode indicators (command line patterns)
FIREFOX_PRIVATE_PATTERNS = [
    "-private-window",  # Standard private window flag
    "--private-window",
    "-private",  # Short form
    "--private",
]

# Browser executable names that support private browsing
PRIVATE_CAPABLE_BROWSERS = {
    # Chrome/Chromium variants
    "chrome", "google-chrome", "google-chrome-stable", "google-chrome-beta", "google-chrome-unstable",
    "chromium", "chromium-browser", "chromium-codecs-ffmpeg-extra",
    # Firefox variants
    "firefox", "firefox-bin", "firefox-esr", "firefox-esr-bin",
    "firefox.real",  # Snap package wrapper
    "snap.firefox",  # Snap package
    # Edge variants
    "msedge", "microsoft-edge", "microsoft-edge-beta", "microsoft-edge-dev",
    # Brave
    "brave", "brave-browser",
    # Opera
    "opera", "opera-beta", "opera-developer",
    # Vivaldi
    "vivaldi", "vivaldi-stable", "vivaldi-snapshot",
}


def _check_incognito(proc) -> bool:
    """Check if a browser process is running in incognito/private mode.
    
    Supports Chrome, Firefox, Edge, Safari, Brave, Opera, Vivaldi.
    Works with snap packages and various browser builds.
    """
    try:
        cmdline = proc.cmdline()
        if not cmdline:
            return False
        
        # Get process name - try multiple methods
        proc_name = ""
        try:
            proc_name = proc.name().lower()
        except:
            pass
        
        # Fallback: get name from cmdline[0]
        if not proc_name and cmdline:
            proc_name = cmdline[0].split('/')[-1].lower()
        
        # Check if it's a known private-capable browser
        is_browser = any(browser in proc_name for browser in PRIVATE_CAPABLE_BROWSERS)
        
        # Join command line for pattern matching
        cmdline_str = " ".join(cmdline).lower()
        full_cmdline = " ".join(cmdline)  # Original case for display
        
        # Debug logging for all browser-like processes
        if 'firefox' in proc_name or 'chrome' in proc_name or 'chromium' in proc_name:
            log.info(f"🔍 BROWSER CHECK: name='{proc_name}', is_browser={is_browser}, cmd={full_cmdline[:120]}")
        
        # Check for incognito/private flags
        for flag in INCOGNITO_FLAGS:
            if flag.lower() in cmdline_str:
                log.info(f"🔒 INCOGNITO DETECTED: {proc_name} with flag {flag}")
                return True
        
        # Firefox-specific: Check for private window patterns
        if 'firefox' in proc_name or 'firefox-bin' in proc_name or 'firefox.real' in proc_name:
            # Check for any private-related pattern
            if any(pattern.lower() in cmdline_str for pattern in FIREFOX_PRIVATE_PATTERNS):
                log.info(f"🔒 FIREFOX PRIVATE WINDOW DETECTED: {proc_name}")
                return True
            # Firefox private windows have specific profile/URL patterns
            if '-no-remote' in full_cmdline and '-profile' not in full_cmdline:
                log.info(f"🔒 FIREFOX PRIVATE MODE (no-profile) DETECTED: {proc_name}")
                return True
            # Check for new-instance without profile (another private mode indicator)
            if '-new-instance' in full_cmdline:
                log.info(f"🔒 FIREFOX NEW-INSTANCE DETECTED: {proc_name}")
                return True
        
        # Chrome/Chromium-specific: Check for guest mode (similar to incognito)
        if any(name in proc_name for name in ['chrome', 'chromium']):
            if '--guest' in full_cmdline or '-guest' in full_cmdline:
                log.info(f"🔒 CHROME GUEST MODE DETECTED: {proc_name}")
                return True
            # Check for temp profile (indicates incognito)
            if '--user-data-dir=' in full_cmdline and 'temp' in full_cmdline.lower():
                log.info(f"🔒 CHROME TEMP PROFILE DETECTED: {proc_name}")
                return True
        
        return False
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception as e:
        log.debug(f"Error checking incognito for {proc.pid}: {e}")
        return False


def _classify_process(proc_info: dict, proc_obj=None) -> dict | None:
    """Classify a process and enrich with risk_level, category, label.
    
    Incognito/private processes are given HIGH risk and labeled appropriately.
    Normal and incognito versions of same browser are treated as different processes.

    Returns None if the process should be filtered out (safe / low priority).
    Returns the enriched dict otherwise.
    """
    name_lower = (proc_info.get("name") or "").lower()

    # Check for incognito/private browsing
    is_incognito = False
    if proc_obj:
        is_incognito = _check_incognito(proc_obj)
    
    if is_incognito:
        proc_info["risk_level"] = "high"
        proc_info["category"] = "incognito"
        # Create browser-specific label
        if 'firefox' in name_lower:
            proc_info["label"] = f"{proc_info.get('name', 'Browser')} (Private Window)"
        else:
            proc_info["label"] = f"{proc_info.get('name', 'Browser')} (Incognito)"
        proc_info["is_incognito"] = True
        return proc_info

    # Safe processes → skip
    if name_lower in SAFE_PROCESSES:
        return None

    if name_lower in DANGEROUS_PROCESSES:
        proc_info["risk_level"] = "high"
        proc_info["category"] = "dangerous"
        # Use the actual process name from PROCESS_LABELS or fallback to the name
        proc_info["label"] = PROCESS_LABELS.get(name_lower, proc_info.get("name", "Unknown Process"))
        proc_info["is_incognito"] = False
        return proc_info

    if name_lower in SUSPICIOUS_PROCESSES:
        proc_info["risk_level"] = "medium"
        proc_info["category"] = "suspicious"
        proc_info["label"] = PROCESS_LABELS.get(name_lower, proc_info.get("name", "Unknown Process"))
        proc_info["is_incognito"] = False
        return proc_info

    # Unknown binary — include only if CPU > threshold
    cpu = proc_info.get("cpu", 0.0)
    if cpu >= UNKNOWN_CPU_THRESHOLD:
        proc_info["risk_level"] = "low"
        proc_info["category"] = "unknown"
        proc_info["label"] = proc_info.get("name", "Unknown Process")
        proc_info["is_incognito"] = False
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
    """Return dict of {pid: info} for all running user processes.
    
    Filters out:
    - System processes (root/system on Linux, SYSTEM/NETWORK SERVICE on Windows)
    - Processes with very low CPU and memory usage
    """
    import getpass
    import os
    
    procs: dict[int, dict] = {}
    current_user = None
    try:
        current_user = getpass.getuser()
    except:
        pass
    
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info", "status", "create_time"]):
        try:
            info = proc.info
            
            # Skip if we can't get the username
            if not info.get("username"):
                continue
            
            username = info["username"] or ""
            username_lower = username.lower()
            
            # Filter out system processes by username
            # Linux: skip root and other system users
            # Windows: skip SYSTEM, NETWORK SERVICE, LOCAL SERVICE
            system_users = {
                "root", "system", "network service", "local service",
                "daemon", "bin", "sys", "sync", "games", "man",
                "lp", "mail", "news", "uucp", "proxy", "www-data",
                "backup", "list", "irc", "gnats", "nobody",
                "systemd-network", "systemd-resolve", "messagebus",
                "_apt", "tss", "kernoops", "whoopsie", "dnsmasq",
                "avahi", "cups-pk-helper", "fwupd", "saned",
                "colord", "speech-dispatcher", "pulse", "rtkit",
                "geoclue", "nm-openvpn", "nm-openconnect",
            }
            
            if username_lower in system_users:
                # Only allow root processes if current user is root
                if username_lower == "root" and current_user and current_user.lower() == "root":
                    pass  # Allow root processes for root user
                else:
                    continue  # Skip all other system user processes
            
            # Skip processes with very low resource usage (likely background)
            cpu = round(info["cpu_percent"] or 0.0, 2)
            memory_mb = round((info["memory_info"].rss if info["memory_info"] else 0) / (1024 * 1024), 2)
            
            # Only include if:
            # 1. Has notable CPU usage (> 0.5%) - lowered from 1%
            # 2. Or uses significant memory (> 30MB) - lowered from 50MB
            # 3. Or is a known suspicious/dangerous process (browsers, terminals, etc.)
            name_lower = (info["name"] or "").lower()
            is_notable = (
                cpu > 0.5 or 
                memory_mb > 30.0 or
                name_lower in DANGEROUS_PROCESSES or
                name_lower in SUSPICIOUS_PROCESSES
            )
            
            if not is_notable:
                continue
            
            procs[info["pid"]] = {
                "pid": info["pid"],
                "name": info["name"] or "unknown",
                "user": username,
                "cpu": cpu,
                "memory": memory_mb,
                "status": info["status"] or "unknown",
                "started_at": info["create_time"],
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs


def _filter_and_classify(snapshot: dict[int, dict], proc_map: dict[int, any] = None) -> list[dict]:
    """Apply classification filter and return only relevant processes."""
    result = []
    for pid, proc in snapshot.items():
        proc_obj = proc_map.get(pid) if proc_map else None
        classified = _classify_process(dict(proc), proc_obj)  # copy so we don't mutate state
        if classified is not None:
            result.append(classified)
    return result


def _diff(prev: dict[int, dict], curr: dict[int, dict], prev_map: dict = None, curr_map: dict = None) -> list[dict]:
    """Compute delta events between two snapshots (with classification)."""
    events: list[dict] = []

    new_pids = set(curr) - set(prev)
    gone_pids = set(prev) - set(curr)

    for pid in new_pids:
        proc_obj = curr_map.get(pid) if curr_map else None
        classified = _classify_process(dict(curr[pid]), proc_obj)
        if classified is not None:
            events.append({
                "type": "process_new",
                "data": classified,
                "meta": _make_meta(classified, f"{classified.get('label', classified['name'])} started"),
            })

    for pid in gone_pids:
        prev_proc = prev[pid]
        proc_obj = prev_map.get(pid) if prev_map else None
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
            proc_obj = curr_map.get(pid) if curr_map else None
            classified = _classify_process(dict(c), proc_obj)
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
    proc_map = {}  # Keep track of process objects for incognito detection

    while True:
        now = time.monotonic()
        curr = _take_snapshot()
        
        # Build a map of current process objects for incognito detection
        curr_proc_map = {}
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                curr_proc_map[proc.info["pid"]] = proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Full snapshot on first run or every SNAPSHOT_INTERVAL
        if now - last_snapshot_ts >= config.SNAPSHOT_INTERVAL or not _prev_snapshot:
            filtered = _filter_and_classify(curr, curr_proc_map)

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
            prev_proc_map = proc_map.copy()
            deltas = _diff(_prev_snapshot, curr, prev_proc_map, curr_proc_map)
            for evt in deltas:
                evt["ts"] = time.time()
                await send_fn(evt)

        _prev_snapshot = curr
        proc_map = curr_proc_map
        await asyncio.sleep(config.DELTA_INTERVAL)
