"""network_monitor.py — Comprehensive network activity monitoring.

Three detection layers run concurrently:

  Layer 1 — ``ss -tnp`` polling (no root required)
      Detects terminal tools (curl, wget, git, ssh …) making live TCP
      connections and resolves remote IPs to hostnames.

  Layer 2 — ``auditd`` log tailing (optional, requires root / read access)
      Parses EXECVE audit records to capture full command + arguments for
      network-capable executables.  Skipped gracefully when the audit log
      is unreadable.

  Legacy — ``psutil``-based domain aggregation (preserved for backward compat)
      Counts unique domain connections and classifies them by risk.

Emits:
  • terminal_request   – Layer 1: terminal tool detected via ss
  • terminal_command   – Layer 2: full command captured via auditd
  • domain_activity    – Legacy:  aggregated domain request counts
  • network_snapshot   – Legacy:  full interface / connection list
  • network_update     – Legacy:  notable connection count change
"""

import asyncio
import logging
import os
import platform
import re
import socket
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

import psutil

from .. import config

log = logging.getLogger("lab_guardian.monitor.network")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONITORED_TOOLS: Set[str] = {
    "curl", "wget", "git", "python", "python3", "pip", "pip3",
    "apt", "apt-get", "ssh", "nc", "ncat", "socat", "node", "npm",
}

SUSPICIOUS_TERMINAL_DOMAINS: Set[str] = {
    "chatgpt.com", "openai.com", "gemini.google.com", "bard.google.com",
    "github.com", "gitlab.com", "pastebin.com", "hastebin.com",
    "stackoverflow.com", "chegg.com", "coursehero.com", "brainly.com",
    "api.telegram.org", "web.whatsapp.com", "discord.com",
    "ngrok.io", "serveo.net",
    "transfer.sh", "file.io",
}

# Subset of SUSPICIOUS_TERMINAL_DOMAINS used for legacy domain_activity
_HIGH_RISK_DOMAINS: Set[str] = {
    "chatgpt.com", "openai.com", "chegg.com", "coursehero.com",
    "brainly.com", "quizlet.com", "bartleby.com",
}

# auditd commands whose execve records we care about
_AUDITD_TOOLS: Set[str] = {
    "curl", "wget", "git", "ssh", "python3", "python", "pip", "pip3",
    "apt", "apt-get", "nc", "ncat", "socat", "node", "npm",
}

# Risk mapping for auditd-captured commands (by tool basename)
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
    """Represents a connection observed via ``ss -tnp``."""
    pid: int
    tool_name: str
    remote_ip: str
    remote_host: Optional[str]
    remote_port: int
    risk_level: str  # "high" | "medium" | "low"


@dataclass
class AuditCommand:
    """Represents a command captured from auditd EXECVE records."""
    tool_name: str
    full_command: str
    risk_level: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

# Layer 1
_seen_connections: Set[Tuple[int, str, int]] = set()  # (pid, remote_ip, port)
_ss_available: Optional[bool] = None

# Layer 2
_audit_file_pos: int = 0
_audit_available: Optional[bool] = None
_seen_audit_keys: Set[str] = set()  # dedup by (timestamp + command hash)

# Legacy
_prev_info: Optional[dict] = None
_domain_counter: dict = defaultdict(int)
_last_connections: Set[tuple] = set()

# Reverse DNS cache
_SKIP_PRIVATE: Set[str] = {"127.0.0.1", "0.0.0.0", "::1", "::"}
_IP_CACHE: dict = {}


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1 — ss-based terminal tool detection
# ═══════════════════════════════════════════════════════════════════════════

def _check_ss_available() -> bool:
    """Test whether the ``ss`` command is available."""
    try:
        subprocess.run(
            ["ss", "--version"],
            capture_output=True,
            timeout=2,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _resolve_ip(ip: str) -> Optional[str]:
    """Best-effort reverse DNS lookup with in-memory cache.

    Returns the resolved hostname or *None* if lookup fails.
    """
    if ip in _SKIP_PRIVATE or not ip:
        return None
    if ip in _IP_CACHE:
        cached = _IP_CACHE[ip]
        return cached if cached != ip else None
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        _IP_CACHE[ip] = host
        return host
    except (socket.herror, socket.gaierror, OSError):
        _IP_CACHE[ip] = ip  # cache negative result
        return None


def _domain_matches_suspicious(hostname: Optional[str]) -> bool:
    """Check if *hostname* (or any parent domain) matches the suspicious list."""
    if hostname is None:
        return False
    h = hostname.lower()
    for sus in SUSPICIOUS_TERMINAL_DOMAINS:
        if h == sus or h.endswith("." + sus):
            return True
    return False


def _extract_root_domain(hostname: str) -> str:
    """Extract the registrable root domain from a FQDN (last two labels)."""
    parts = hostname.rstrip(".").split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname


def _parse_ss_output(raw: str) -> List[SSConnection]:
    """Parse ``ss -tnp`` output into a list of :class:`SSConnection`.

    Example ss line::

        ESTAB  0  0  10.0.0.5:42318  140.82.121.4:443  users:(("curl",pid=12345,fd=3))
    """
    results: List[SSConnection] = []
    # Regex to extract process info from the users:(...) column
    proc_re = re.compile(r'\("([^"]+)",pid=(\d+)')

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("State"):
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        state = parts[0]
        if state != "ESTAB":
            continue

        # Peer address is the 5th field (index 4)
        peer = parts[4]
        # Handle IPv6 bracket notation: [::1]:port
        if peer.startswith("["):
            bracket_end = peer.rfind("]")
            if bracket_end == -1:
                continue
            remote_ip = peer[1:bracket_end]
            remote_port_str = peer[bracket_end + 2:]  # skip ]:
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

        # Skip loopback / private ranges we don't care about
        if remote_ip in _SKIP_PRIVATE:
            continue

        # Extract process info — may be in parts[5] or later
        users_str = " ".join(parts[5:])
        match = proc_re.search(users_str)
        if not match:
            continue

        tool_name = match.group(1)
        pid = int(match.group(2))

        # Determine risk level
        if tool_name in MONITORED_TOOLS:
            risk_level = "high"
        else:
            risk_level = "medium"

        # Resolve hostname
        remote_host = _resolve_ip(remote_ip)

        # Escalate if suspicious domain
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
    """Run ``ss -tnp`` and return only NEW connections since last poll."""
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
        log.debug("ss returned exit code %d", result.returncode)
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
    """Check whether the auditd log is readable."""
    path = config.AUDITD_LOG_PATH
    if not os.path.isfile(path):
        return False
    return os.access(path, os.R_OK)


def _init_audit_position() -> int:
    """Seek to the end of the audit log so we only capture *new* entries."""
    try:
        return os.path.getsize(config.AUDITD_LOG_PATH)
    except OSError:
        return 0


def _parse_execve_args(line: str) -> Optional[str]:
    """Reconstruct the full command from EXECVE audit record arguments.

    EXECVE records contain fields like::

        a0="curl" a1="https://chatgpt.com/api/..." a2="-o" a3="/dev/null"

    Hex-encoded arguments (a0=6375726C) are also decoded.
    """
    args: dict = {}
    arg_re = re.compile(r'a(\d+)=("?)([^"\s]+)"?')
    for m in arg_re.finditer(line):
        idx = int(m.group(1))
        val = m.group(3)
        # Decode hex-encoded arguments (no quotes, all hex chars)
        if not m.group(2) and all(c in "0123456789abcdefABCDEF" for c in val) and len(val) % 2 == 0 and len(val) >= 2:
            try:
                val = bytes.fromhex(val).decode("utf-8", errors="replace")
            except (ValueError, UnicodeDecodeError):
                pass
        args[idx] = val

    if not args:
        return None

    return " ".join(args[i] for i in sorted(args))


def _tail_audit_log() -> List[AuditCommand]:
    """Read new lines from the auditd log since last position.

    Returns a list of :class:`AuditCommand` for network-capable executables.
    """
    global _audit_file_pos

    path = config.AUDITD_LOG_PATH
    commands: List[AuditCommand] = []

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

    # Build a mapping: audit event serial → list of lines
    # We care about type=EXECVE lines that contain our monitored tool names
    for line in new_data.splitlines():
        if "type=EXECVE" not in line:
            continue

        # Reconstruct command
        full_cmd = _parse_execve_args(line)
        if not full_cmd:
            continue

        # Extract the tool basename
        cmd_parts = full_cmd.split()
        if not cmd_parts:
            continue
        tool_path = cmd_parts[0]
        tool_name = os.path.basename(tool_path)

        if tool_name not in _AUDITD_TOOLS:
            continue

        # Dedup key — prevent firing the same command twice
        dedup_key = full_cmd.strip()
        if dedup_key in _seen_audit_keys:
            continue
        _seen_audit_keys.add(dedup_key)

        # Limit the dedup set size to prevent unbounded memory growth
        if len(_seen_audit_keys) > 10000:
            # Keep only the most recent half
            _seen_audit_keys.clear()

        risk = _AUDITD_RISK_MAP.get(tool_name, "medium")

        # Check if any argument contains a suspicious domain
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
# Legacy — psutil-based domain aggregation (preserved for backward compat)
# ═══════════════════════════════════════════════════════════════════════════

def _get_interfaces() -> list:
    """Return list of network interfaces with IP addresses."""
    interfaces: list = []
    try:
        import netifaces  # noqa: E402
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
    """Parse DNS servers from /etc/resolv.conf (Linux/macOS)."""
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
    """Count established TCP connections."""
    try:
        conns = psutil.net_connections(kind="tcp")
        return sum(1 for c in conns if c.status == "ESTABLISHED")
    except (psutil.AccessDenied, OSError):
        return -1


def _collect_legacy() -> dict:
    """Collect legacy network info (IP, gateway, DNS, connection count)."""
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


def _collect_domains() -> None:
    """Scan ESTABLISHED TCP connections and aggregate domain counts."""
    global _last_connections
    try:
        conns = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, OSError):
        return

    current: set = set()
    for c in conns:
        if c.status != "ESTABLISHED":
            continue
        raddr = c.raddr
        if not raddr:
            continue
        remote_ip = raddr.ip
        remote_port = raddr.port
        conn_key = (remote_ip, remote_port, c.pid)
        current.add(conn_key)
        if conn_key not in _last_connections:
            domain = _resolve_ip(remote_ip)
            if domain:
                root = _extract_root_domain(domain)
                _domain_counter[root] += 1

    _last_connections = current


def _flush_domain_counter() -> list:
    """Return accumulated domain counts and reset."""
    global _domain_counter
    if not _domain_counter:
        return []
    result = [
        {"domain": d, "count": c}
        for d, c in sorted(_domain_counter.items(), key=lambda x: -x[1])
    ]
    _domain_counter = defaultdict(int)
    return result


def _classify_domain(domain: str) -> str:
    """Return risk level for a domain."""
    if domain.lower() in _HIGH_RISK_DOMAINS:
        return "high"
    if domain.lower() in SUSPICIOUS_TERMINAL_DOMAINS:
        return "medium"
    return "normal"


# ═══════════════════════════════════════════════════════════════════════════
# Event builders
# ═══════════════════════════════════════════════════════════════════════════

def _build_ss_event(conn: SSConnection) -> dict:
    """Build event envelope for a terminal request detected via ss."""
    host_display = conn.remote_host or conn.remote_ip
    if conn.remote_host:
        root = _extract_root_domain(conn.remote_host)
        host_display = root

    message = (
        f"\u26a0\ufe0f TERMINAL REQUEST DETECTED  |  "
        f"{conn.tool_name} \u2192 {conn.remote_ip} ({host_display}):{conn.remote_port}"
    )
    if conn.risk_level != "high":
        message = (
            f"Terminal Connection  |  "
            f"{conn.tool_name} \u2192 {conn.remote_ip} ({host_display}):{conn.remote_port}"
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
    """Build event envelope for a command captured via auditd."""
    message = (
        f"\u26a0\ufe0f TERMINAL CMD DETECTED  |  {cmd.full_command}"
    )
    if cmd.risk_level not in ("high",):
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
    """Long-running coroutine for comprehensive network monitoring.

    *send_fn* is an ``async def send(event: dict)`` callback used to
    dispatch events to the WebSocket layer.

    Runs Layer 1 (ss), Layer 2 (auditd), and legacy domain aggregation
    concurrently, with graceful degradation if tools are unavailable.
    """
    global _prev_info, _ss_available, _audit_available, _audit_file_pos

    log.info("Network monitor started")

    # ── Capability detection ──
    _ss_available = _check_ss_available()
    if _ss_available:
        log.info("Layer 1 (ss) — active, polling every %d s", config.NETWORK_SS_INTERVAL)
    else:
        log.warning("Layer 1 (ss) — UNAVAILABLE, terminal connection detection disabled")

    _audit_available = _check_audit_available()
    if _audit_available:
        _audit_file_pos = _init_audit_position()
        log.info("Layer 2 (auditd) — active, tailing %s", config.AUDITD_LOG_PATH)
    else:
        log.warning(
            "Layer 2 (auditd) — UNAVAILABLE, terminal command capture disabled. "
            "Run with sudo or: sudo chmod o+r %s",
            config.AUDITD_LOG_PATH,
        )

    last_snapshot_ts = 0.0
    last_ss_ts = 0.0
    _prev_info = None

    while True:
        now = time.monotonic()
        loop = asyncio.get_event_loop()

        # ── Layer 1: ss-based terminal tool detection ──
        if _ss_available and (now - last_ss_ts >= config.NETWORK_SS_INTERVAL):
            new_conns = await loop.run_in_executor(None, _poll_ss)
            for conn in new_conns:
                event = _build_ss_event(conn)
                await send_fn(event)
            last_ss_ts = now

        # ── Layer 2: auditd log tailing ──
        if _audit_available:
            audit_cmds = await loop.run_in_executor(None, _tail_audit_log)
            for cmd in audit_cmds:
                event = _build_audit_event(cmd)
                await send_fn(event)

        # ── Legacy: domain aggregation + network snapshot ──
        info = await loop.run_in_executor(None, _collect_legacy)
        await loop.run_in_executor(None, _collect_domains)

        # Legacy network_snapshot (DEPRECATED — kept for backward compat)
        if now - last_snapshot_ts >= config.SNAPSHOT_INTERVAL or _prev_info is None:
            await send_fn({
                "type": "network_snapshot",
                "data": info,
                "ts": time.time(),
                "meta": {
                    "risk_level": "low",
                    "category": "network",
                    "message": "Network snapshot (legacy)",
                },
            })
            last_snapshot_ts = now
        else:
            prev_conn = (_prev_info or {}).get("activeConnections", 0)
            curr_conn = info.get("activeConnections", 0)
            if abs(curr_conn - prev_conn) >= 3:
                await send_fn({
                    "type": "network_update",
                    "data": info,
                    "ts": time.time(),
                    "meta": {
                        "risk_level": "low",
                        "category": "network",
                        "message": "Network connections changed",
                    },
                })

        # Domain activity events
        domain_data = _flush_domain_counter()
        if domain_data:
            for entry in domain_data:
                entry["risk_level"] = _classify_domain(entry["domain"])

            has_high = any(d["risk_level"] == "high" for d in domain_data)
            await send_fn({
                "type": "domain_activity",
                "data": domain_data,
                "ts": time.time(),
                "meta": {
                    "risk_level": "high" if has_high else "normal",
                    "category": "network",
                    "message": f"{len(domain_data)} domain(s) accessed",
                },
            })

        _prev_info = info

        # Sleep at the shorter of the two poll intervals so ss fires on time
        sleep_interval = config.NETWORK_SS_INTERVAL if _ss_available else config.NETWORK_POLL_INTERVAL
        await asyncio.sleep(sleep_interval)
