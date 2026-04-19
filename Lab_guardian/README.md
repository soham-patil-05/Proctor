# Lab Guardian — Offline-First Exam Monitoring Agent

A lightweight Python agent that runs on student lab machines and monitors
**processes, connected devices, network connections, terminal activity, and browser history**
with **100% offline operation**. All data is stored locally in SQLite and automatically synced
to the backend when internet becomes available.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Student Machine (Ubuntu)                             │
│                                                       │
│  ┌──────────────────────────────────────┐           │
│  │ Agent UI (PyQt5)                      │           │
│  │ - Roll No + Lab No input             │           │
│  │ - Real-time activity display         │           │
│  │ - Status indicators                  │           │
│  └──────────────┬───────────────────────┘           │
│                 ↓                                    │
│  ┌──────────────────────────────────────┐           │
│  │ Local SQLite (~/.lab_guardian/)      │           │
│  │ - All data stored locally first      │           │
│  │ - Works 100% offline                 │           │
│  └──────────────┬───────────────────────┘           │
│                 ↓ (when internet available)          │
│  ┌──────────────────────────────────────┐           │
│  │ Sync Manager                          │           │
│  │ - Uploads unsynced logs via HTTP     │           │
│  │ - Retries automatically              │           │
│  └──────────────────────────────────────┘           │
└─────────────────────┬───────────────────────────────┘
                      ↓ HTTP POST /api/logs/receive
              Backend Server (Node.js + PostgreSQL)
```

---

## Requirements

- Python ≥ 3.9
- Linux (Ubuntu recommended) with PyQt5
- `iproute2` package (provides `ss` command) — pre-installed on Ubuntu
- Optional: `auditd` for full terminal command capture (requires root)

## Quick Start

```bash
# 1. Install dependencies and auditd rules (requires sudo)
sudo bash setup.sh

# Or without auditd:
bash setup.sh --no-auditd

# 2. Start the exam monitoring agent
lab_guardian start

# Or with custom backend URL:
lab_guardian start --api-url http://your-server:8000 -vv
```

## What It Does

1. **Student enters details** → Roll Number + Lab Number in PyQt5 UI
2. **Creates local exam session** → Stored in SQLite at `~/.lab_guardian/exam_data.db`
3. **Monitors run concurrently**:

| Monitor          | What it tracks                              | Interval |
|------------------|---------------------------------------------|----------|
| Process          | Running processes with risk levels          | 30 s     |
| Device           | USB/external device connections             | 2 s      |
| Network (ss)     | Terminal tool network connections           | 2 s      |
| Network (auditd) | Full terminal commands (optional, root)     | 2 s      |
| Browser History  | Visited URLs (Chrome, Firefox, Edge, Brave) | 10 s     |

4. **All data saved locally** → Works 100% offline during exam
5. **Auto-sync when internet available** → Uploads to backend every 30 seconds
6. **Session end** → Teacher provides secret key (80085) to end session

## Monitoring Features

### Process Monitoring
- Tracks all running processes
- Identifies high-risk applications (browsers, communication tools)
- Detects incognito/private browsing modes
- Append-only logging (no data deletion during exam)

### USB Device Detection
- Real-time USB device connection/disconnection
- Identifies device type and brand
- Flags external storage devices

### Network Monitoring (Two Layers)

**Layer 1: Active Connection Polling via `ss` (No Root Required)**
- Runs `ss -tnp` every 2 seconds
- Detects terminal tools making network connections (curl, wget, git, ssh, etc.)
- Reverse-DNS lookup with caching
- Flags suspicious domains automatically

**Layer 2: auditd Log Tailing (Optional, Root Required)**
- Captures full terminal commands with arguments
- Parses auditd EXECVE records
- Detects commands accessing suspicious domains

**Monitored Tools:**
`curl`, `wget`, `git`, `python`, `python3`, `pip`, `pip3`, `apt`, `apt-get`,
`ssh`, `nc`, `ncat`, `socat`, `node`, `npm`

**Suspicious Domains (auto-flagged as HIGH risk):**
```
chatgpt.com, openai.com, gemini.google.com, bard.google.com,
github.com, gitlab.com, pastebin.com, hastebin.com,
stackoverflow.com, chegg.com, coursehero.com, brainly.com,
api.telegram.org, web.whatsapp.com, discord.com,
ngrok.io, serveo.net, transfer.sh, file.io
```

### Browser History
- Extracts visited URLs from:
  - Google Chrome
  - Mozilla Firefox
  - Microsoft Edge
  - Brave Browser
- Tracks page titles and visit counts
- Detects incognito/private windows

## Configuration

All settings can be configured via **environment variables**:

| Env variable              | Default | Description                     |
|---------------------------|---------|---------------------------------|
| `LAB_GUARDIAN_API_URL`    | `http://localhost:8000` | Backend HTTP base URL |
| `LG_SNAPSHOT_INTERVAL`    | `30`    | Process snapshot interval (sec) |
| `LG_DELTA_INTERVAL`       | `3`     | Process delta interval (sec)    |
| `LG_DEVICE_POLL_INTERVAL` | `2`     | Device poll interval (sec)      |
| `LG_NETWORK_SS_INTERVAL`  | `2`     | ss connection poll interval     |
| `LG_AUDITD_LOG_PATH`      | `/var/log/audit/audit.log` | auditd log file path |

## Offline-First Design

### How It Works

1. **Local Storage First**
   - All monitoring data is immediately saved to local SQLite
   - Agent works 100% offline — no internet required during exam
   - Data stored in `~/.lab_guardian/exam_data.db`

2. **Automatic Sync**
   - Sync manager checks internet connectivity every 10 seconds
   - When internet is available, uploads all unsynced records
   - Sends batch POST to `/api/logs/receive` endpoint
   - Marks local records as synced after successful upload
   - Automatically retries on failure

3. **Status Indicators**
   - **Monitoring** (green) — Agent actively monitoring
   - **Internet** (green/red) — Internet connectivity status
   - **Sync** (green/yellow) — Sync status with backend

### Sync Data Flow

```
Local SQLite → Collect unsynced records → HTTP POST → Backend
     ↓                                          ↓
 Mark as synced ← 200 OK ← Store in PostgreSQL
```

## auditd Setup (Optional)

For full terminal command capture:

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

## Debian Package

Build the `.deb` installer:

```bash
cd Lab_guardian
chmod +x build_deb.sh
./build_deb.sh
```

This creates: `build/deb/lab-guardian-agent-2.0.0.deb`

Install on student machines:

```bash
sudo dpkg -i lab-guardian-agent-2.0.0.deb
sudo apt-get install -f   # resolve dependencies
```

The package includes:
- ✅ Python 3 virtual environment with all dependencies
- ✅ PyQt5 GUI
- ✅ All monitoring modules
- ✅ System-wide `lab-guardian` command
- ✅ Desktop application entry
- ✅ Automatic configuration

## Package Structure

```
Lab_guardian/
├── setup.py
├── setup.sh                    # Dependency installer + auditd rules
├── build_deb.sh               # Debian package builder
├── requirements.txt
├── lab_guardian/
│   ├── __init__.py             # __version__
│   ├── __main__.py             # Module entry point
│   ├── cli.py                  # argparse entry point
│   ├── config.py               # env-based defaults
│   ├── agent_ui.py             # PyQt5 GUI
│   ├── local_db.py             # SQLite database management
│   ├── sync_manager.py         # Offline-first sync logic
│   ├── dispatcher.py           # Orchestrates all monitors
│   └── monitor/
│       ├── __init__.py
│       ├── process_monitor.py  # psutil-based process tracking
│       ├── device_monitor.py   # USB / block device monitoring
│       ├── network_monitor.py  # ss + auditd network monitoring
│       └── browser_history.py  # Browser history extraction
├── systemd/
│   └── lab_guardian.service
└── debian/
    ├── control
    ├── postinst
    └── prerm
```

## Local Database Schema

Stored in `~/.lab_guardian/exam_data.db` (SQLite):

**exam_sessions**: Tracks exam instances
- `id`, `roll_no`, `lab_no`, `start_time`, `end_time`, `secret_key_verified`, `synced`

**local_processes**: Process monitoring data
- `session_id`, `pid`, `process_name`, `cpu_percent`, `memory_mb`, `status`, `risk_level`, `synced`

**local_devices**: USB device tracking
- `session_id`, `device_id`, `device_name`, `device_type`, `readable_name`, `synced`

**local_terminal_events**: Terminal commands
- `session_id`, `tool`, `full_command`, `remote_ip`, `risk_level`, `synced`

**local_browser_history**: Browser URLs
- `session_id`, `url`, `title`, `visit_count`, `last_visited`, `browser`, `synced`

## Troubleshooting

### Agent won't start
```bash
# Check if Python 3.9+ is installed
python3 --version

# Check if PyQt5 is installed
python3 -c "import PyQt5"

# Reinstall the package
sudo dpkg -r lab-guardian-agent
sudo dpkg -i lab-guardian-agent-2.0.0.deb
```

### Data not syncing
```bash
# Check internet connectivity
ping 8.8.8.8

# Check backend URL
cat /etc/lab-guardian/config

# View agent logs
journalctl -f | grep lab_guardian
```

### Database issues
```bash
# Check database file
ls -lh ~/.lab_guardian/exam_data.db

# Check database integrity
sqlite3 ~/.lab_guardian/exam_data.db "PRAGMA integrity_check;"
```

## Graceful Degradation

- If `ss` is not available → Network Layer 1 skipped, warning logged
- If audit.log is not readable → Network Layer 2 skipped, note printed
- If backend is unreachable → Data stored locally, sync retries automatically
- The agent **never crashes** due to missing capabilities

## License

MIT
