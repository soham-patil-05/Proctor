# Lab Guardian — Student Agent

A lightweight Python agent that runs on student lab machines and reports
**processes, connected devices, network connections, and terminal activity**
to the [Lab Insight](../backend/README.md) backend in real time over WebSocket.

---

## Requirements

- Python ≥ 3.9
- Linux recommended (pyudev for USB event detection); works on macOS/Windows with polling fallback
- `iproute2` package (provides `ss` command) — pre-installed on Ubuntu
- Optional: `auditd` for full terminal command capture (requires root)

## Quick Start

```bash
# 1. Install (with auditd rules — requires sudo)
sudo bash setup.sh

# Or without auditd:
bash setup.sh --no-auditd

# 2. Join a live session (interactive prompts for roll number / session ID)
lab_guardian join

# Or pass everything on the command line:
lab_guardian join \
  --roll-no CS2021001 \
  --session-id <UUID> \
  --password optional-password \
  --api-url http://10.0.0.5:8000 \
  --ws-url ws://10.0.0.5:8001 \
  -vv
```

## What It Does

1. **HTTP join** → `POST /api/students/join-session` with `rollNo` + `sessionId`  
   Receives a short-lived JWT (1 h) containing `studentId`, `sessionId`, `role: "student"`.

2. **WebSocket connect** → `ws://<host>:8001/ws/agents/sessions/<sessionId>/students/<studentId>?token=<jwt>`  
   Server replies with an `ack` event containing recommended intervals.

3. **Monitors** run concurrently:

| Monitor   | What it reports                                | Snapshot interval | Delta interval |
|-----------|------------------------------------------------|:-----------------:|:--------------:|
| Process   | PIDs, names, CPU %, memory, status             | 30 s              | 3 s            |
| Device    | Mounted partitions / USB devices               | 30 s              | 2 s (poll)     |
| Network   | Interfaces, IPs, gateway, DNS, TCP connections | 30 s              | 5 s            |
| Network (ss) | Terminal tool connections (curl, wget, git…) | —                 | 2 s            |
| Network (auditd) | Full terminal commands with args          | —                 | 2 s (tail)     |

4. **Heartbeat** sent every 5 s (configurable). Server marks agent offline after 15 s of silence.

5. **Reconnect** with exponential backoff (1 s → 60 s max) + jitter.

## Event Types Sent

| `type`                | Source          | Description                                      |
|-----------------------|-----------------|--------------------------------------------------|
| `processes_snapshot`  | Process monitor | Full process list                                |
| `process_new`         | Process monitor | New PID appeared                                 |
| `process_update`      | Process monitor | CPU/mem changed beyond threshold                 |
| `process_end`         | Process monitor | PID disappeared                                  |
| `devices_snapshot`    | Device monitor  | Full disk/partition list                         |
| `device_connected`    | Device monitor  | New device detected                              |
| `device_disconnected` | Device monitor  | Device removed                                   |
| `network_snapshot`    | Network monitor | Full network state (legacy)                      |
| `network_update`      | Network monitor | Connection count changed significantly (legacy)  |
| `domain_activity`     | Network monitor | Aggregated domain request counts                 |
| `terminal_request`    | Network (ss)    | Terminal tool detected making a TCP connection    |
| `terminal_command`    | Network (auditd)| Full command + args captured from audit log       |
| `heartbeat`           | WS client       | Keep-alive (every 5 s)                           |

### Terminal Request Event (Layer 1 — ss)

Detected when a monitored tool (`curl`, `wget`, `git`, `ssh`, `pip`, etc.)
opens a TCP connection. No root required.

```json
{
    "type": "terminal_request",
    "data": {
        "tool": "curl",
        "remote_ip": "140.82.121.4",
        "remote_host": "lb-140-82-121-4-iad.github.com",
        "remote_port": 443,
        "pid": 12345
    },
    "ts": 1712500000.0,
    "meta": {
        "risk_level": "high",
        "category": "network",
        "message": "⚠️ TERMINAL REQUEST DETECTED  |  curl → 140.82.121.4 (github.com):443"
    }
}
```

### Terminal Command Event (Layer 2 — auditd)

Captures the full command line from auditd EXECVE records. Requires `auditd`
to be installed and the audit log to be readable.

```json
{
    "type": "terminal_command",
    "data": {
        "tool": "git",
        "full_command": "git clone https://github.com/answers/repo"
    },
    "ts": 1712500001.0,
    "meta": {
        "risk_level": "high",
        "category": "network",
        "message": "⚠️ TERMINAL CMD DETECTED  |  git clone https://github.com/answers/repo"
    }
}
```

## Network Monitor — Detection Layers

### Layer 1: Active Connection Polling via `ss` (No Root Required)

- Runs `ss -tnp` every 2 seconds
- Parses ESTABLISHED connections to extract PID, process name, remote IP/port
- Reverse-DNS lookup on remote IPs with caching
- Deduplicates connections by `(pid, remote_ip, remote_port)` tuple
- Flags connections from monitored tools as HIGH risk
- Escalates ANY connection to HIGH if the resolved domain matches the suspicious list

**Monitored Tools:**
`curl`, `wget`, `git`, `python`, `python3`, `pip`, `pip3`, `apt`, `apt-get`,
`ssh`, `nc`, `ncat`, `socat`, `node`, `npm`

### Layer 2: auditd Log Tailing (Optional, Root Required)

- Reads `/var/log/audit/audit.log` from the current file position (tail -f style)
- Parses EXECVE audit records to reconstruct full command + arguments
- Handles both quoted and hex-encoded arguments
- Deduplicates commands per session
- Escalates risk to HIGH if command contains a suspicious domain

**Risk Mapping:**

| Tool | Risk Level |
|------|:----------:|
| curl, wget, git, ssh, nc, ncat, socat | HIGH |
| python, python3, pip, pip3, node, npm | MEDIUM |
| apt, apt-get | LOW |

### Suspicious Domains

Connections or commands involving these domains are automatically escalated to HIGH:

```
chatgpt.com, openai.com, gemini.google.com, bard.google.com,
github.com, gitlab.com, pastebin.com, hastebin.com,
stackoverflow.com, chegg.com, coursehero.com, brainly.com,
api.telegram.org, web.whatsapp.com, discord.com,
ngrok.io, serveo.net, transfer.sh, file.io
```

### Graceful Degradation

- If `ss` is not available → Layer 1 skipped, warning logged at startup
- If audit.log is not readable → Layer 2 skipped, startup note printed
- The agent **never crashes** due to missing network monitoring capabilities

## auditd Setup

```bash
# Install auditd
sudo apt install auditd

# Add persistent rules
sudo bash setup.sh

# Or manually:
sudo auditctl -a always,exit -F arch=b64 -S execve -F exe=/usr/bin/curl    -k exam_net
sudo auditctl -a always,exit -F arch=b64 -S execve -F exe=/usr/bin/wget    -k exam_net
sudo auditctl -a always,exit -F arch=b64 -S execve -F exe=/usr/bin/git     -k exam_net
sudo auditctl -a always,exit -F arch=b64 -S execve -F exe=/usr/bin/ssh     -k exam_net
sudo auditctl -a always,exit -F arch=b64 -S execve -F exe=/usr/bin/python3 -k exam_net

# Make audit log readable (if not running agent as root)
sudo chmod o+r /var/log/audit/audit.log
```

Rules are persisted in `/etc/audit/rules.d/exam.rules` and survive reboots.

## Configuration

All knobs can be set via **environment variables** or overridden by the server's `ack` payload:

| Env variable              | Default | Description                     |
|---------------------------|---------|---------------------------------|
| `LAB_GUARDIAN_API_URL`    | `http://localhost:8000` | Backend HTTP base URL |
| `LAB_GUARDIAN_WS_URL`     | `ws://localhost:8001`   | Backend WS base URL   |
| `LG_SNAPSHOT_INTERVAL`    | `30`    | Full snapshot interval (sec)    |
| `LG_DELTA_INTERVAL`       | `3`     | Process delta interval (sec)    |
| `LG_DEVICE_POLL_INTERVAL` | `2`     | Device poll interval (sec)      |
| `LG_NETWORK_POLL_INTERVAL`| `5`     | Legacy network poll interval    |
| `LG_NETWORK_SS_INTERVAL`  | `2`     | ss connection poll interval     |
| `LG_AUDITD_LOG_PATH`      | `/var/log/audit/audit.log` | auditd log file path |
| `LG_HEARTBEAT_INTERVAL`   | `5`     | Heartbeat send interval (sec)   |

## systemd Service

```bash
sudo cp systemd/lab_guardian.service /etc/systemd/system/
sudo mkdir -p /etc/lab_guardian
echo "ROLL_NO=CS2021001\nSESSION_ID=<uuid>" | sudo tee /etc/lab_guardian/env
sudo systemctl enable --now lab_guardian
```

## Debian Package

Build with `dpkg-deb`:

```bash
dpkg-deb --build lab_guardian lab-guardian_1.0.0_all.deb
```

Install:

```bash
sudo dpkg -i lab-guardian_1.0.0_all.deb
sudo apt-get install -f   # resolve deps
```

## Package Structure

```
Lab_guardian/
├── setup.py
├── setup.sh                    # Dependency installer + auditd rules
├── requirements.txt
├── lab_guardian/
│   ├── __init__.py             # __version__
│   ├── cli.py                  # argparse entry point
│   ├── config.py               # env-based defaults
│   ├── api.py                  # HTTP join-session client
│   ├── ws_client.py            # WebSocket + reconnect + heartbeat
│   ├── dispatcher.py           # orchestrates monitors → ws_client
│   └── monitor/
│       ├── __init__.py
│       ├── process_monitor.py  # psutil-based process tracking
│       ├── device_monitor.py   # USB / block device monitoring
│       └── network_monitor.py  # ss + auditd + domain aggregation
├── systemd/
│   └── lab_guardian.service
└── debian/
    ├── control
    ├── postinst
    └── prerm
```

## License

MIT
