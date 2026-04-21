"""network_monitor.py — Terminal command monitoring.

Three detection layers run concurrently:

  Layer 1 — ``ss -tnp`` polling (no root required)
      Detects terminal tools (curl, wget, git, ssh …) making live TCP
      connections.

  Layer 2 — ``auditd`` log tailing (optional, requires root / read access)
      Parses EXECVE audit records to capture full command + arguments for
      network-capable executables.  Skipped gracefully when the audit log
      is unreadable.
      Also handles log rotation: if the file shrinks (rotated), the read
      position is reset to 0 automatically.

  Layer 3 — psutil process scanning (no root required, always active)
      Scans the process list every poll cycle and detects short-lived
      commands (git status, git log, python script.py, etc.) that finish
      too quickly for ss to catch. Uses cmdline() to reconstruct the full
      command and deduplicates by (pid, create_time) so each execution is
      emitted exactly once.

Note: Browser history is handled by browser_history.py module.

Emits:
  • terminal_request   — Layer 1: terminal tool detected via ss
  • terminal_command   — Layer 2: full command captured via auditd
  • terminal_command   — Layer 3: command captured via psutil scan

Changes in this version
-----------------------
1. Layer 3 now filters by username — only events from the current user are
   emitted.  System-owned processes (root, www-data, daemon, etc.) are
   silently skipped.

2. SYSTEM_CMD_PATTERNS blocklist — Layer 3 skips commands whose path or
   arguments match known system-maintenance patterns (update-manager, apport,
   dpkg, unattended-upgrade, etc.).

3. PSUTIL_MONITORED_TOOLS — Layer 3 uses a separate set that excludes
   apt/apt-get.  Package managers generate near-100% system noise in a lab
   environment.  Layer 1 and Layer 2 keep apt/apt-get in their own sets.

4. Minimum argument filter — bare interpreter invocations (python3 with no
   script) are skipped; ssh with no arguments IS still emitted (suspicious).

5. Dedup set caps reduced: _seen_audit_keys 10 000 → 2 000;
   _seen_psutil_keys 20 000 → 2 000.

6. Auditd log-rotation resilience: if current file size < _audit_file_pos,
   the position is reset to 0 so we don't miss new entries after rotation.
"""

import asyncio
import getpass
import logging
import os
import platform
import re
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

import psutil

from .. import config

log = logging.getLogger("lab_guardian.monitor.network")

# ---------------------------------------------------------------------------
# Current-user identification (computed once at module load)
# ---------------------------------------------------------------------------

def _get_current_user() -> str:
    try:
        return getpass.getuser().lower()
    except Exception:
        return ""

_CURRENT_USER: str = _get_current_user()

# Accounts whose processes should NEVER generate terminal events
_SYSTEM_USERS: frozenset = frozenset({
    "root", "system", "network service", "local service", "daemon",
    "www-data", "nobody", "messagebus", "syslog", "_apt", "man",
    "landscape", "pollinate", "uuidd", "sshd", "systemd-resolve",
    "systemd-network", "systemd-timesync", "ntp", "avahi", "colord",
    "rtkit", "speech-dispatcher", "kernoops", "cups-pk-helper",
    "whoopsie", "hplip", "geoclue", "gnome-initial-setup",
})

# ---------------------------------------------------------------------------
# Tool sets
# ---------------------------------------------------------------------------

# Layer 1 (ss) + Layer 2 (auditd) — unchanged, keeps apt/apt-get
MONITORED_TOOLS: Set[str] = {
    "curl", "wget", "git", "python", "python3", "pip", "pip3",
    "apt", "apt-get", "ssh", "nc", "ncat", "socat", "node", "npm",
}

# Layer 3 (psutil) — excludes package managers (system noise in lab)
PSUTIL_MONITORED_TOOLS: Set[str] = {
    "curl", "wget", "git", "python", "python3", "pip", "pip3",
    "ssh", "nc", "ncat", "socat", "node", "npm",
}

# ---------------------------------------------------------------------------
# System command path blocklist (Layer 3 only)
# ---------------------------------------------------------------------------

# If the full command string contains ANY of these substrings (case-sensitive),
# the event is silently dropped.  These are well-known system-maintenance
# invocations that carry zero academic-integrity signal.
SYSTEM_CMD_PATTERNS: Tuple[str, ...] = (
    "/usr/lib/update-manager/",
    "/usr/share/apport/",
    "/usr/lib/gnome-",
    "/usr/lib/apt/",
    "/usr/lib/packagekit/",
    "/usr/bin/dpkg",
    "/usr/sbin/",
    "check-new-release",
    "unattended-upgrade",
    "apt-get update",
    "apt-get -q",
    "apt list",
    "/usr/lib/python3/dist-packages/",
    "/usr/share/ubuntu-advantage-tools/",
    "/usr/lib/ubuntu-advantage/",
    "/usr/bin/ubuntu-advantage",
    "/snap/core",
    "snap refresh",
)

# ---------------------------------------------------------------------------
# Suspicious domain sets
# ---------------------------------------------------------------------------

SUSPICIOUS_TERMINAL_DOMAINS: Set[str] = {
    "chatgpt.com", "openai.com", "gemini.google.com", "bard.google.com",
    "github.com", "gitlab.com", "pastebin.com", "hastebin.com",
    "stackoverflow.com", "chegg.com", "coursehero.com", "brainly.com",
    "api.telegram.org", "web.whatsapp.com", "discord.com",
    "ngrok.io", "serveo.net",
    "transfer.sh", "file.io",
}

_HIGH_RISK_DOMAINS: Set[str] = {
    "chatgpt.com", "openai.com", "chegg.com", "coursehero.com",
    "brainly.com", "quizlet.com", "bartleby.com",
}

_AUDITD_TOOLS: Set[str] = {
    "curl", "wget", "git", "ssh", "python3", "python", "pip", "pip3",
    "apt", "apt-get", "nc", "ncat", "socat", "node", "npm",
}

_AUDITD_RISK_MAP: dict = {
    "curl":    "high",
    "wget":    "high",
    "git":     "high",
    "ssh":     "high",
    "python":  "medium",
    "python3": "medium",
    "pip":     "medium",
    "pip3":    "medium",
    "apt":     "low",
    "apt-get": "low",
    "nc":      "high",
    "ncat":    "high",
    "socat":   "high",
    "node":    "medium",
    "npm":     "medium",
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SSConnection:
    pid: int
    tool_name: str
    remote_ip: str
    remote_host: Optional[str]
    remote_port: int
    risk_level: str


@dataclass
class AuditCommand:
    tool_name: str
    full_command: str
    risk_level: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

# Layer 1
_seen_connections: Set[Tuple[int, str, int]] = set()
_ss_available: Optional[bool] = None

# Layer 2
_audit_file_pos: int = 0
_audit_available: Optional[bool] = None
_seen_audit_keys: Set[str] = set()

# Layer 3
_seen_psutil_keys: Set[Tuple[int, float]] = set()

# Reverse DNS cache
_SKIP_PRIVATE: Set[str] = {"127.0.0.1", "0.0.0.0", "::1", "::"}
_IP_CACHE: dict = {}


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1 — ss-based terminal tool detection
# ═══════════════════════════════════════════════════════════════════════════

def _check_ss_available() -> bool:
    try:
        subprocess.run(["ss", "--version"], capture_output=True, timeout=2)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _resolve_ip(ip: str) -> Optional[str]:
    if ip in _IP_CACHE:
        return _IP_CACHE[ip]
    try:
        host = socket.gethostbyaddr(ip)[0]
        _IP_CACHE[ip] = host
        return host
    except Exception:
        _IP_CACHE[ip] = None
        return None


def _extract_root_domain(hostname: Optional[str]) -> str:
    if not hostname:
        return ""
    parts = hostname.rstrip(".").split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname


def _domain_matches_suspicious(hostname: Optional[str]) -> bool:
    if not hostname:
        return False
    root = _extract_root_domain(hostname)
    return root in SUSPICIOUS_TERMINAL_DOMAINS or hostname in SUSPICIOUS_TERMINAL_DOMAINS


def _parse_ss_output(raw: str) -> List[SSConnection]:
    results: List[SSConnection] = []
    proc_re = re.compile(r'\("([^"]+)",pid=(\d+)')

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("State"):
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        if parts[0] != "ESTAB":
            continue

        peer = parts[4]
        if peer.startswith("["):
            bracket_end = peer.rfind("]")
            if bracket_end == -1:
                continue
            remote_ip = peer[1:bracket_end]
            remote_port_str = peer[bracket_end + 2:]
        else:
            last_colon = peer.rfind(":")
            if last_colon == -1:
                continue
            remote_ip = peer[:last_colon]
            remote_port_str = peer[last_colon + 1:]

        try:
            remote_port = int(remote_port_str)
        except ValueError:
            continue

        if remote_ip in _SKIP_PRIVATE:
            continue

        users_str = " ".join(parts[5:])
        match = proc_re.search(users_str)
        if not match:
            continue

        tool_name = match.group(1)
        pid = int(match.group(2))

        risk_level = "high" if tool_name in MONITORED_TOOLS else "medium"
        remote_host = _resolve_ip(remote_ip)
        if _domain_matches_suspicious(remote_host):
            risk_level = "high"

        results.append(SSConnection(
            pid=pid,
            tool_name=tool_name,
            remote_ip=remote_ip,
            remote_host=remote_host,
            remote_port=remote_port,
            risk_level=risk_level,
        ))

    return results


def _poll_ss() -> List[SSConnection]:
    global _seen_connections

    try:
        result = subprocess.run(
            ["ss", "-tnp"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        log.debug("ss poll failed: %s", exc)
        return []

    if result.returncode != 0:
        return []

    all_conns = _parse_ss_output(result.stdout)
    new_conns: List[SSConnection] = []
    current_keys: Set[Tuple[int, str, int]] = set()

    for conn in all_conns:
        key = (conn.pid, conn.remote_ip, conn.remote_port)
        current_keys.add(key)
        if key not in _seen_connections:
            new_conns.append(conn)

    _seen_connections = current_keys
    return new_conns


# ═══════════════════════════════════════════════════════════════════════════
# Layer 2 — auditd log tailing
# ═══════════════════════════════════════════════════════════════════════════

def _check_audit_available() -> bool:
    path = config.AUDITD_LOG_PATH
    if not os.path.isfile(path):
        return False
    return os.access(path, os.R_OK)


def _init_audit_position() -> int:
    try:
        return os.path.getsize(config.AUDITD_LOG_PATH)
    except OSError:
        return 0


def _parse_execve_args(line: str) -> Optional[str]:
    args: dict = {}
    arg_re = re.compile(r'a(\d+)=("?)([^"\s]+)"?')
    for m in arg_re.finditer(line):
        idx = int(m.group(1))
        val = m.group(3)
        if (
            not m.group(2)
            and all(c in "0123456789abcdefABCDEF" for c in val)
            and len(val) % 2 == 0
            and len(val) >= 2
        ):
            try:
                val = bytes.fromhex(val).decode("utf-8", errors="replace")
            except (ValueError, UnicodeDecodeError):
                pass
        args[idx] = val

    if not args:
        return None
    return " ".join(args[i] for i in sorted(args))


def _tail_audit_log() -> List[AuditCommand]:
    global _audit_file_pos

    path = config.AUDITD_LOG_PATH
    commands: List[AuditCommand] = []

    # Log-rotation resilience: if the file is smaller than our saved position,
    # the log was rotated — reset to start of the new file.
    try:
        current_size = os.path.getsize(path)
        if current_size < _audit_file_pos:
            log.info("auditd log rotation detected; resetting read position to 0")
            _audit_file_pos = 0
    except OSError:
        pass

    try:
        with open(path, "r", errors="replace") as f:
            f.seek(_audit_file_pos)
            new_data = f.read()
            _audit_file_pos = f.tell()
    except (OSError, PermissionError) as exc:
        log.debug("Cannot read audit log: %s", exc)
        return commands

    if not new_data:
        return commands

    for line in new_data.splitlines():
        if "type=EXECVE" not in line:
            continue

        if any(skip in line.lower() for skip in [
            "exe=\"/usr/sbin/cron\"",
            "exe=\"/lib/systemd/\"",
            "exe=\"/usr/lib/systemd/\"",
            "auid=4294967295",
        ]):
            continue

        full_cmd = _parse_execve_args(line)
        if not full_cmd:
            continue

        cmd_parts = full_cmd.split()
        if not cmd_parts:
            continue
        tool_name = os.path.basename(cmd_parts[0])

        if tool_name not in _AUDITD_TOOLS:
            continue

        dedup_key = full_cmd.strip()
        if dedup_key in _seen_audit_keys:
            continue
        _seen_audit_keys.add(dedup_key)

        # Reduced cap: 2 000 is ample for a 3-hour exam session
        if len(_seen_audit_keys) > 2000:
            _seen_audit_keys.clear()

        risk = _AUDITD_RISK_MAP.get(tool_name, "medium")
        for sus in SUSPICIOUS_TERMINAL_DOMAINS:
            if sus in full_cmd.lower():
                risk = "high"
                break

        commands.append(AuditCommand(
            tool_name=tool_name,
            full_command=full_cmd,
            risk_level=risk,
        ))

    return commands


# ═══════════════════════════════════════════════════════════════════════════
# Layer 3 — psutil process scanning (catches short-lived commands)
# ═══════════════════════════════════════════════════════════════════════════

def _poll_psutil_processes() -> List[AuditCommand]:
    """Scan all running processes and detect student-owned monitored tool executions.

    Improvements over the previous version:
    - Only emits events for processes owned by the current user (not root/system).
    - Skips commands matching SYSTEM_CMD_PATTERNS (update-manager, apport, etc.).
    - Uses PSUTIL_MONITORED_TOOLS (no apt/apt-get) to avoid package-manager noise.
    - Skips bare interpreter invocations with no arguments (system helpers).
    - Dedup set cap reduced from 20 000 to 2 000.
    """
    global _seen_psutil_keys

    new_commands: List[AuditCommand] = []
    current_keys: Set[Tuple[int, float]] = set()

    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time", "username"]):
            try:
                info = proc.info
                name        = info.get("name") or ""
                cmdline     = info.get("cmdline") or []
                pid         = info.get("pid")
                create_time = info.get("create_time") or 0.0
                username    = (info.get("username") or "").lower()

                if not name or not cmdline or pid is None:
                    continue

                # ── Username filter ──────────────────────────────────────────
                # Skip processes owned by known system accounts.
                if username in _SYSTEM_USERS:
                    continue
                # Only emit events for the current interactive user.
                # If we can't determine the current user, allow all non-system users.
                if _CURRENT_USER and username and username != _CURRENT_USER:
                    continue

                # ── Tool name filter ─────────────────────────────────────────
                tool_name = os.path.basename(name)
                if tool_name not in PSUTIL_MONITORED_TOOLS:
                    # Also check the first cmdline element (wrapper scripts)
                    if cmdline:
                        first = os.path.basename(cmdline[0])
                        if first not in PSUTIL_MONITORED_TOOLS:
                            continue
                        tool_name = first

                # ── Minimum argument filter ──────────────────────────────────
                # Bare interpreter calls (python3 with no script) are almost
                # always system helpers.  ssh/nc/curl with zero args are
                # unusual enough to flag — keep them.
                if tool_name in {"python", "python3", "node", "perl", "ruby", "pip", "pip3"} \
                        and len(cmdline) < 2:
                    continue

                # ── Dedup ────────────────────────────────────────────────────
                create_key = round(create_time, 2)
                key = (pid, create_key)
                current_keys.add(key)

                if key in _seen_psutil_keys:
                    continue

                # ── Build full command string ────────────────────────────────
                full_cmd = " ".join(str(a) for a in cmdline if a)

                # ── System command path filter ───────────────────────────────
                if any(pat in full_cmd for pat in SYSTEM_CMD_PATTERNS):
                    # Still track the key so we don't re-evaluate this process
                    _seen_psutil_keys.add(key)
                    continue

                # ── Risk classification ──────────────────────────────────────
                risk = _AUDITD_RISK_MAP.get(tool_name, "medium")
                for sus in SUSPICIOUS_TERMINAL_DOMAINS:
                    if sus in full_cmd.lower():
                        risk = "high"
                        break

                new_commands.append(AuditCommand(
                    tool_name=tool_name,
                    full_command=full_cmd,
                    risk_level=risk,
                    timestamp=create_time,
                ))

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as exc:
        log.debug("psutil scan error: %s", exc)

    # Merge current keys into seen set; cap at 2 000 to bound memory usage.
    _seen_psutil_keys = _seen_psutil_keys | current_keys
    if len(_seen_psutil_keys) > 2000:
        # Keep only the keys still alive in this scan cycle.
        _seen_psutil_keys = current_keys

    return new_commands


# ═══════════════════════════════════════════════════════════════════════════
# Legacy — psutil-based network info collection
# ═══════════════════════════════════════════════════════════════════════════

def _get_interfaces() -> list:
    interfaces: list = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            ipv4_list = addrs.get(netifaces.AF_INET, [])
            ipv4 = ipv4_list[0]["addr"] if ipv4_list else None
            gateways = netifaces.gateways()
            default_gw = None
            if "default" in gateways and netifaces.AF_INET in gateways["default"]:
                default_gw = gateways["default"][netifaces.AF_INET][0]
            interfaces.append({"name": iface, "ipv4": ipv4, "gateway": default_gw})
    except ImportError:
        for name, addrs in psutil.net_if_addrs().items():
            ipv4 = None
            for a in addrs:
                if a.family.name == "AF_INET":
                    ipv4 = a.address
                    break
            interfaces.append({"name": name, "ipv4": ipv4, "gateway": None})
    return interfaces


def _get_dns_servers() -> list:
    servers: list = []
    if platform.system() in ("Linux", "Darwin"):
        try:
            with open("/etc/resolv.conf") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) >= 2:
                            servers.append(parts[1])
        except OSError:
            pass
    return servers


def _get_active_connections() -> int:
    try:
        conns = psutil.net_connections(kind="tcp")
        return sum(1 for c in conns if c.status == "ESTABLISHED")
    except (psutil.AccessDenied, OSError):
        return -1


def _collect_legacy() -> dict:
    interfaces = _get_interfaces()
    primary_ip = None
    primary_gw = None
    for iface in interfaces:
        if iface.get("ipv4") and not iface["ipv4"].startswith("127."):
            primary_ip = iface["ipv4"]
            primary_gw = iface.get("gateway")
            break
    return {
        "ip": primary_ip,
        "gateway": primary_gw,
        "dns": _get_dns_servers(),
        "activeConnections": _get_active_connections(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Event builders
# ═══════════════════════════════════════════════════════════════════════════

def _build_ss_event(conn: SSConnection) -> Optional[dict]:
    browser_processes = {
        'chrome', 'chromium', 'firefox', 'msedge', 'brave',
        'opera', 'vivaldi', 'safari', 'epiphany',
    }
    if conn.tool_name.lower() in browser_processes:
        return None

    host_display = conn.remote_host or conn.remote_ip
    if conn.remote_host:
        root = _extract_root_domain(conn.remote_host)
        host_display = root

    if conn.risk_level == "high":
        message = (
            f"⚠️ TERMINAL REQUEST DETECTED  |  "
            f"{conn.tool_name} → {conn.remote_ip} ({host_display}):{conn.remote_port}"
        )
    else:
        message = (
            f"Terminal Connection  |  "
            f"{conn.tool_name} → {conn.remote_ip} ({host_display}):{conn.remote_port}"
        )

    return {
        "type": "terminal_request",
        "data": {
            "tool": conn.tool_name,
            "remote_ip": conn.remote_ip,
            "remote_host": conn.remote_host,
            "remote_port": conn.remote_port,
            "pid": conn.pid,
        },
        "ts": time.time(),
        "meta": {
            "risk_level": conn.risk_level,
            "category": "network",
            "message": message,
        },
    }


def _build_audit_event(cmd: AuditCommand) -> dict:
    if cmd.risk_level == "high":
        message = f"⚠️ TERMINAL CMD DETECTED  |  {cmd.full_command}"
    else:
        message = f"Terminal Command  |  {cmd.full_command}"

    return {
        "type": "terminal_command",
        "data": {
            "tool": cmd.tool_name,
            "full_command": cmd.full_command,
        },
        "ts": cmd.timestamp,
        "meta": {
            "risk_level": cmd.risk_level,
            "category": "network",
            "message": message,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Main coroutine
# ═══════════════════════════════════════════════════════════════════════════

async def run(send_fn):
    """Long-running coroutine for comprehensive network and terminal monitoring."""
    global _ss_available, _audit_available, _audit_file_pos

    log.info("Network monitor started (current user: %s)", _CURRENT_USER or "<unknown>")

    _ss_available = _check_ss_available()
    if _ss_available:
        log.info("Layer 1 (ss) — active, polling every %d s", config.NETWORK_SS_INTERVAL)
    else:
        log.warning("Layer 1 (ss) — UNAVAILABLE")

    _audit_available = _check_audit_available()
    if _audit_available:
        _audit_file_pos = _init_audit_position()
        log.info("Layer 2 (auditd) — active, tailing %s", config.AUDITD_LOG_PATH)
    else:
        log.warning(
            "Layer 2 (auditd) — UNAVAILABLE. "
            "Run: sudo chmod o+r %s",
            config.AUDITD_LOG_PATH,
        )

    log.info("Layer 3 (psutil) — active, scanning every %d s", config.NETWORK_SS_INTERVAL)

    last_snapshot_ts = 0.0
    last_ss_ts = 0.0
    last_psutil_ts = 0.0

    while True:
        now = time.monotonic()
        loop = asyncio.get_event_loop()

        # ── Layer 1: ss-based terminal tool detection ──
        if _ss_available and (now - last_ss_ts >= config.NETWORK_SS_INTERVAL):
            try:
                new_conns = await loop.run_in_executor(None, _poll_ss)
                for conn in new_conns:
                    event = _build_ss_event(conn)
                    if event:
                        await send_fn(event)
            except Exception as e:
                log.debug("ss polling error: %s", e)
            last_ss_ts = now

        # ── Layer 2: auditd log tailing ──
        if _audit_available:
            try:
                audit_cmds = await loop.run_in_executor(None, _tail_audit_log)
                for cmd in audit_cmds:
                    await send_fn(_build_audit_event(cmd))
            except Exception as e:
                log.debug("auditd tailing error: %s", e)

        # ── Layer 3: psutil process scanning ──
        if now - last_psutil_ts >= config.NETWORK_SS_INTERVAL:
            try:
                psutil_cmds = await loop.run_in_executor(None, _poll_psutil_processes)
                for cmd in psutil_cmds:
                    await send_fn(_build_audit_event(cmd))
            except Exception as e:
                log.debug("psutil scan error: %s", e)
            last_psutil_ts = now

        # ── Network snapshot (IP info) ──
        if now - last_snapshot_ts >= 60:
            try:
                info = await loop.run_in_executor(None, _collect_legacy)
                await send_fn({
                    "type": "network_snapshot",
                    "data": info,
                    "ts": time.time(),
                    "meta": {
                        "risk_level": "low",
                        "category": "network",
                        "message": "Network info snapshot",
                    },
                })
            except Exception as e:
                log.debug("network snapshot error: %s", e)
            last_snapshot_ts = now

        sleep_interval = min(config.NETWORK_SS_INTERVAL, 2)
        await asyncio.sleep(sleep_interval)