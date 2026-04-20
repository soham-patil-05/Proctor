# LabGuardian Client Application

## 1. Project Overview

LabGuardian Client is a desktop-side monitoring agent designed for controlled lab or exam environments. It runs on the student machine, continuously captures local telemetry, stores it safely in local SQLite, presents it to invigilators through a local Tkinter dashboard, and exports unsynced records to the LabGuardian backend API.

### What this client does

- Captures process, device, terminal, and browser telemetry from the local machine.
- Normalizes telemetry into a strict canonical contract before storage.
- Persists telemetry in SQLite so no data is lost during transient network issues.
- Shows live session data in four tabs (Devices, Network, Processes, Terminal).
- Exports unsynced data to backend endpoint `/api/telemetry/ingest`.
- Marks local rows as synced only after backend success confirmation.

### Role in the overall LabGuardian system

- The client is the telemetry producer and local source of truth during a session.
- Backend is the central aggregator and query surface for examiner-facing apps.
- Frontend dashboards consume backend responses; they do not read client local DB directly.

### Primary use cases

- Proctored lab sessions where suspicious software usage must be tracked.
- Exam environments where terminal/network misuse needs auditing.
- Offline/unstable network conditions requiring reliable local buffering before upload.

---

## 2. Tech Stack

## Language and Runtime

- Python 3.9+
  - Chosen for cross-platform system introspection ecosystem and fast iteration for monitor logic.

## Desktop UI

- Tkinter (stdlib)
  - Chosen to avoid heavyweight UI dependencies and keep packaging straightforward.
  - Allows direct native desktop app behavior for session lifecycle and invigilator interactions.

## Local Storage

- SQLite3 (stdlib)
  - Chosen for embedded durability, zero external dependency, transactional consistency, and easy inspection/debugging.

## Monitoring and System Telemetry

- psutil
  - Process stats, disk partitions, network connections, interface introspection.
- pyudev (Linux-focused)
  - Event-driven device monitoring for attach/remove behavior.
- ss command (iproute2)
  - Terminal connection detection at socket level without requiring root for basic visibility.
- auditd log parsing
  - Captures executed terminal commands with argument-level detail when audit permissions are available.

## Networking

- requests
  - Reliable HTTP client for export with timeout handling and robust exception branches.

## Packaging and Deployment

- setuptools / pip editable install
  - Standard Python packaging and command-line entry point generation.
- systemd service file
  - Production daemonization support on Linux.
- Debian control/postinst/prerm scripts
  - OS-native installation and lifecycle management.

---

## 3. Complete Project Structure (Client)

```text
Lab_guardian/
├── README.md
├── requirements.txt
├── setup.py
├── setup.sh
├── test_browser_paths.py
├── test_firefox_history.py
├── debian/
│   ├── control
│   ├── postinst
│   └── prerm
├── systemd/
│   └── lab_guardian.service
├── lab_guardian/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── dispatcher.py
│   ├── gui.py
│   └── monitor/
│       ├── __init__.py
│       ├── browser_history.py
│       ├── device_monitor.py
│       ├── network_monitor.py
│       └── process_monitor.py
└── lab_guardian.egg-info/
    ├── dependency_links.txt
    ├── entry_points.txt
    ├── PKG-INFO
    ├── requires.txt
    ├── SOURCES.txt
    └── top_level.txt
```

---

## 4. File-by-File Analysis

## Root files

### README.md
- Purpose: documentation for client setup and internals.
- Interaction: developer onboarding reference.
- Key logic: none (docs only).

### requirements.txt
- Purpose: runtime dependency list.
- Interaction: consumed by setup.py and setup.sh installation path.
- Key entries:
  - psutil
  - requests
  - netifaces
  - pyudev

### setup.py
- Purpose: package metadata and console script entrypoint.
- Interaction:
  - Loads requirements.txt
  - Creates command `lab_guardian=lab_guardian.gui:main`
- Key logic:
  - defines package as `lab_guardian`
  - minimum Python `>=3.9`

### setup.sh
- Purpose: bootstrap script for Linux deployment and optional auditd setup.
- Interaction:
  - Installs apt packages (`python3`, `iproute2`, optional `auditd`)
  - Installs Python package editable mode
  - Writes audit rules for command capture
- Key logic:
  - supports `--no-auditd`
  - performs service/audit checks and informative output

### test_browser_paths.py
- Purpose: environment diagnostic for browser history DB discovery.
- Interaction: standalone troubleshooting script for monitor path issues.
- Key logic:
  - checks common browser DB locations
  - prints found/not found and size details

### test_firefox_history.py
- Purpose: deep debug helper for Firefox timestamp conversion and query behavior.
- Interaction: standalone validation script for browser_history monitor correctness.
- Key logic:
  - copies places.sqlite to temp
  - prints sample rows and converted timestamps
  - verifies filtering after a reference timestamp

## debian/

### debian/control
- Purpose: Debian package metadata.
- Interaction: package managers and build tools.
- Key logic:
  - declares dependencies and package description.

### debian/postinst
- Purpose: post-install steps.
- Interaction:
  - installs package via pip
  - installs systemd service file
- Key logic:
  - calls `systemctl daemon-reload`
  - prompts enable/start instructions

### debian/prerm
- Purpose: pre-removal cleanup.
- Interaction:
  - stops/disables service
  - removes service file
  - uninstalls package
- Key logic: safe cleanup with fallback `|| true` style.

## systemd/

### systemd/lab_guardian.service
- Purpose: run agent as system service.
- Interaction:
  - executes CLI using env file values (`ROLL_NO`, `SESSION_ID`)
  - restarts on failure
- Key logic:
  - hardened sandboxing settings
  - read-only access to audit log path for terminal command layer

## lab_guardian package

### lab_guardian/__init__.py
- Purpose: package marker + version definition.
- Interaction: imported by tooling/tests if needed.
- Key logic: defines `__version__`.

### lab_guardian/config.py
- Purpose: central configuration and environment variable binding.
- Interaction:
  - imported by monitor, GUI, dispatcher
  - controls API URL, poll intervals, thresholds
- Key logic:
  - derives backend host/port from API base URL
  - stores monitor cadence and risk threshold constants

### lab_guardian/db.py
- Purpose: canonical local persistence layer.
- Interaction:
  - dispatcher writes here
  - GUI reads from here
  - export reads unsynced and marks sync status
- Key logic:
  - creates canonical tables:
    - sessions
    - usb_devices
    - browser_history
    - processes
    - terminal_events
  - thread-safe with global lock
  - normalization helpers for risk, numbers, JSON
  - merge/upsert behavior:
    - browser history uses max visit_count and max last_visited
    - process filtering excludes safe/ended states at storage boundary
  - retrieval APIs:
    - get_all_for_session
    - get_unsynced
    - mark_synced

### lab_guardian/dispatcher.py
- Purpose: async event orchestrator and normalization gateway.
- Interaction:
  - receives monitor events from process/device/network/browser modules
  - writes normalized records to db.py
- Key logic:
  - queue-based fan-in and backpressure handling
  - per-event normalization:
    - device id/readable_name/message/risk/metadata
    - process cpu/memory/name field harmonization
    - terminal detected_at/tool fallback logic
    - browser ms-to-seconds timestamp normalization
  - canonical handler routing:
    - devices_snapshot/device_connected/device_disconnected
    - process_snapshot/process_new/process_update/process_end
    - terminal_request/terminal_command/terminal_events_snapshot
    - browser_history

### lab_guardian/gui.py
- Purpose: desktop application shell and operational control plane.
- Interaction:
  - starts/stops dispatcher runtime in dedicated thread + event loop
  - periodically queries db.py and paints tabs
  - exports unsynced payload to backend via requests
- Key logic:
  - start screen: roll/name/session/lab input
  - session screen: four telemetry tabs
  - end-session dialog with password gate
  - refresh loop via `root.after(...)`
  - export worker thread with connectivity probing and robust error handling

## lab_guardian/monitor

### lab_guardian/monitor/__init__.py
- Purpose: namespace marker.
- Interaction: package import clarity.
- Key logic: none.

### lab_guardian/monitor/process_monitor.py
- Purpose: process telemetry producer.
- Interaction:
  - emits snapshot/new/update/end events to dispatcher callback
- Key logic:
  - classifies process risk into high/medium/low/safe-like branches
  - detects incognito/private browser flags from cmdline
  - tracks previous snapshots for delta generation
  - emits periodic snapshot and high-frequency deltas

### lab_guardian/monitor/device_monitor.py
- Purpose: USB device telemetry producer.
- Interaction:
  - emits device snapshots and connect/disconnect deltas
- Key logic:
  - filters to USB-like removable devices
  - enriches metadata with mountpoint/size/vendor/model
  - emits canonical device events
  - uses pyudev where available, otherwise polling fallback

### lab_guardian/monitor/network_monitor.py
- Purpose: terminal activity telemetry producer.
- Interaction:
  - emits terminal_request and terminal_command events
- Key logic:
  - Layer 1: `ss -tnp` socket correlation to tool/pid/remote endpoint
  - Layer 2: auditd EXECVE parsing for full command reconstruction
  - deduplicates noisy command repeats
  - marks risk based on tool and suspicious domain presence

### lab_guardian/monitor/browser_history.py
- Purpose: browser URL telemetry producer.
- Interaction:
  - scans browser DB files and returns entries since agent start time
- Key logic:
  - supports Chrome, Chromium, Brave, Edge, Firefox
  - per-browser timestamp format conversion
  - copies DB to temp to avoid lock conflicts
  - returns URL/title/visit_count/last_visited/browser sorted by recency

## lab_guardian.egg-info

These are generated packaging artifacts. They are not runtime logic but are useful for release/debugging.

### dependency_links.txt
- Purpose: legacy dependency links metadata.
- Current state: empty.

### entry_points.txt
- Purpose: generated console script mapping.
- Key content: `lab_guardian = lab_guardian.gui:main`.

### PKG-INFO
- Purpose: resolved package metadata at build/install time.

### requires.txt
- Purpose: generated dependency list used by tooling.

### SOURCES.txt
- Purpose: source manifest used during packaging.
- Note: appears stale because it references files not currently present (`api.py`, `cli.py`, `ws_client.py`), indicating a historical package layout.

### top_level.txt
- Purpose: top-level package list (`lab_guardian`).

---

## 5. Detailed Internals for Core Files

## db.py internals

### Why it is central

All monitor outputs and all GUI reads pass through db.py. It is the data consistency boundary.

### Example: browser upsert merge strategy

```python
INSERT INTO browser_history (...) VALUES (...)
ON CONFLICT(session_id, roll_no, url)
DO UPDATE SET
  title = COALESCE(excluded.title, browser_history.title),
  visit_count = MAX(browser_history.visit_count, excluded.visit_count),
  last_visited = MAX(COALESCE(browser_history.last_visited, 0), COALESCE(excluded.last_visited, 0)),
  browser = COALESCE(excluded.browser, browser_history.browser),
  synced = 0
```

This ensures monotonic counters/timestamps and avoids regressions from partial scans.

### Data flow

- Write path: dispatcher -> db upsert/replace/insert
- Read path: gui refresh loop -> get_all_for_session
- Export path: gui export -> get_unsynced -> backend success -> mark_synced

## dispatcher.py internals

### Why it exists

Monitors may emit slightly different field names or metadata shapes. Dispatcher normalizes before DB writes.

### Normalization examples

- Process fields:
  - cpu from cpu or cpu_percent
  - memory from memory or memory_mb
  - name from name or process_name
- Terminal fields:
  - detected_at fallback from event timestamp or utc now
  - tool fallback to `unknown`
- Browser history:
  - converts millisecond timestamps to seconds when needed

### Runtime model

- Creates async queue with maxsize.
- Each monitor pushes to queue via callback.
- drain coroutine consumes and routes events to db.

## gui.py internals

### Runtime boundary

- Tkinter main thread handles UI.
- Async monitors run in dedicated background thread with event loop.
- Export uses worker thread to avoid UI freeze.

### Session lifecycle

1. Start button validates roll/name/session/lab.
2. start_session writes metadata into local DB.
3. MonitorRuntime starts dispatcher.
4. refresh_session_view runs every monitor interval and repaints tabs.
5. End session stops runtime and records ended_at.

### Export flow

```text
GUI export click
  -> probe backend reachability
  -> db.get_unsynced(session_id, roll_no)
  -> build payload { sessionId, rollNo, labNo, name, devices, browserHistory, processes, terminalEvents }
  -> POST /api/telemetry/ingest
  -> if success == true: db.mark_synced(session_id, roll_no)
```

---

## 6. Application Flow (End-to-End)

## High-level flow

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                        LabGuardian Client Runtime                       │
└──────────────────────────────────────────────────────────────────────────┘
           │
           ▼
User starts session in Tkinter UI
           │
           ▼
Dispatcher starts monitor coroutines
           │
           ├── process_monitor  ── emits process_* events
           ├── device_monitor   ── emits device_* events
           ├── network_monitor  ── emits terminal_* events
           └── browser_history  ── emits browser_history events
           │
           ▼
Dispatcher normalization + routing
           │
           ▼
SQLite canonical tables (unsynced = 0 initially)
           │
           ├── GUI refresh loop reads current rows for live display
           └── Export action reads unsynced rows for upload
                       │
                       ▼
             POST /api/telemetry/ingest
                       │
                       ▼
            success=true -> mark_synced(...)
```

## Per-refresh UI flow

```text
root.after(interval)
  -> db.get_all_for_session(...)
  -> build grouped views
  -> repaint 4 tabs
  -> schedule next root.after(interval)
```

---

## 7. Core Functionalities

## Authentication and access control

- Backend authentication is not implemented in this client module.
- Local session termination is guarded by EndSessionDialog password check.
- Service mode can be controlled by OS permissions (systemd + env file ownership).

## Monitoring and proctoring logic

- Processes:
  - risk-based classification and filtering
  - new/update/end event tracking
- Devices:
  - removable USB discovery
  - vendor/model + storage metadata enrichment
- Terminal:
  - socket-level detection for active terminal network requests
  - auditd command-level detection where available
- Browser history:
  - cross-browser DB scanning with timestamp conversion

## Real-time behavior

- Yes, near-real-time updates are implemented.
- Event-driven + polling hybrid:
  - snapshot cadence (configurable)
  - delta cadence for process changes
  - terminal and browser periodic scanning

## UI/UX behavior

- Start screen captures session identity fields.
- Session notebook has four tabs aligned with canonical contract.
- Empty-state messages and risk-colored rows/cards improve operator scanning.

---

## 8. How It Works Internally

## Lifecycle model

- App startup: create GUI root, init DB schema.
- Session start: persist session, start monitor runtime thread.
- Active session: periodic UI refresh from SQLite.
- Export events: explicit user action, network retries by manual re-trigger.
- Session end: stop runtime, set ended_at.

## State handling

- UI state stored in Tkinter StringVar and in-memory runtime attributes.
- Telemetry state persisted primarily in SQLite tables.
- Monitor runtime state managed in module-level caches for diffs/dedup.

## API integration

- Endpoint: `/api/telemetry/ingest`.
- Payload built from unsynced records only.
- Success criterion: HTTP 2xx and JSON `{ "success": true }`.

## Error handling strategy

- Network reachability pre-probe before export.
- Explicit handling for timeout, connection, HTTP, and generic exceptions.
- Non-fatal monitor failures logged and retried by loop continuity.

---

## 9. Setup and Installation

## Prerequisites

- Python 3.9+
- Linux recommended for full monitor coverage (pyudev, auditd, ss)
- Windows support is partial for some monitors and browser paths

## Local development setup

```bash
cd Lab_guardian
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Run app:

```bash
lab_guardian
```

## Quick bootstrap on Linux

```bash
bash setup.sh
```

Without auditd:

```bash
bash setup.sh --no-auditd
```

## Environment variables

- LAB_GUARDIAN_API_URL
- LAB_GUARDIAN_BACKEND_HOST
- LAB_GUARDIAN_BACKEND_PORT
- LG_LOCAL_DB_PATH
- LG_SNAPSHOT_INTERVAL
- LG_DELTA_INTERVAL
- LG_DEVICE_POLL_INTERVAL
- LG_NETWORK_POLL_INTERVAL
- LG_NETWORK_SS_INTERVAL
- LG_AUDITD_LOG_PATH
- LG_HEARTBEAT_INTERVAL

## Service deployment (systemd)

1. Install package + unit.
2. Configure `/etc/lab_guardian/env` with `ROLL_NO` and `SESSION_ID`.
3. Enable service:

```bash
sudo systemctl enable --now lab_guardian
```

---

## 10. Best Practices Used

- Clear separation of concerns:
  - monitor modules produce events
  - dispatcher normalizes/routs
  - db persists/queries
  - gui presents/exports
- Local-first durability:
  - telemetry persisted before remote export
- Thread-safe persistence:
  - SQLite lock protects concurrent monitor/UI/export access
- Canonical contract enforcement at dispatcher and DB levels
- Defensive parsing and fallback defaults for unstable data sources
- Operator-focused empty states and risk color semantics

---

## 11. Architecture and Data Flow Diagrams

## Module architecture

```text
                         +----------------------+
                         |      gui.py          |
                         |  (Tkinter Runtime)   |
                         +----------+-----------+
                                    |
                    refresh/export  |  start/stop
                                    v
                         +----------+-----------+
                         |       db.py          |
                         |   SQLite Contract    |
                         +----------+-----------+
                                    ^
                                    | normalized writes
                         +----------+-----------+
                         |    dispatcher.py     |
                         | queue + event router |
                         +----+----+----+-------+
                              |    |    |
                              |    |    +--------------------+
                              |    |                         |
                              v    v                         v
                     process_monitor  device_monitor   network_monitor
                                                   \
                                                    \
                                                     v
                                                browser_history
```

## Export sequence

```text
[User clicks Export]
   -> probe backend
   -> read unsynced rows
   -> POST /api/telemetry/ingest
   -> success true ? mark_synced : keep unsynced
```

---

## 12. Operational Notes and Known Gaps

- `lab_guardian.egg-info/SOURCES.txt` appears stale and references files not present in current tree.
- No token-based authentication mechanism is implemented in this client export flow.
- Feature coverage is highest on Linux due to auditd and pyudev dependencies.
- Browser history DB access relies on readable profile files and can vary by browser profile state.

---

## 13. Developer Tips

- Inspect local data quickly:

```bash
python -c "import sqlite3; c=sqlite3.connect('labguardian_local.db'); print(c.execute('select count(*) from processes').fetchone()); c.close()"
```

- Validate browser path detection:

```bash
python test_browser_paths.py
```

- Debug Firefox timestamp behavior:

```bash
python test_firefox_history.py
```

---

This README is intentionally implementation-driven and aligned with the current client source layout in this repository.
