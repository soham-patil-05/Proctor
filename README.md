# LabGuardian - Real-Time Lab Session Monitoring System

A comprehensive, full-stack monitoring solution for computer labs that enables teachers to create and manage lab sessions while tracking student activity in real-time. The system consists of three main components: a **React frontend** for teachers, a **Node.js backend** with REST and WebSocket APIs, and a **Python agent** that runs on student machines to collect and stream telemetry data.

---

## Latest Features (v2.0)

### Process Monitoring Enhancements
- **Process Grouping**: Processes with the same name are now grouped together in the UI, showing instance count and aggregated CPU/memory usage
- **Incognito/Private Browsing Detection**: Automatically detects when students use Chrome's Incognito, Firefox's Private Browsing, or Edge's InPrivate mode
- **Human-Readable Labels**: Processes display friendly names (e.g., "Google Chrome" instead of "chrome.exe", "Bash Shell" instead of "bash")
- **System Process Filtering**: Only shows user-started processes, automatically filtering out root/system processes
- **Smart Resource Thresholds**: Tracks processes with >0.5% CPU or >30MB memory (lowered from 1% CPU / 50MB)

### Network Monitoring Improvements
- **Browser History Integration**: Scans browser SQLite databases to retrieve full URLs visited (not just domains)
  - Supports: Google Chrome, Chromium, Mozilla Firefox, Microsoft Edge, Brave
  - Displays: Full URL, page title, visit count, last visit time, browser name
- **Domain Tracking**: Monitors actual websites accessed on web ports (80, 443, 8080, 8443)
- **Infrastructure Filtering**: Automatically filters out CDN/infrastructure domains (1e100.net, cloudfront.net, akamai.net, etc.)
- **Reverse DNS with Fallback**: Resolves IPs to domain names, falls back to IP if DNS fails

### Terminal Monitoring Refinements
- **User Commands Only**: Filters out system commands (cron, systemd, etc.)
- **Browser Activity Exclusion**: Terminal section no longer shows browser network activity
- **Risk Classification**: Tools like curl, wget, git flagged as high-risk; python/node as medium-risk

### UI/UX Improvements
- **Network Tab Reorganization**: Shows "Top Domains Accessed" first, then "Browser History" below
- **Connection Status Reliability**: Improved WebSocket heartbeat (30s timeout instead of 10s) reduces false "Connection Lost" indicators
- **Process Display**: Grouped processes show all PIDs, total CPU%, and total memory usage

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [System Components](#system-components)
4. [How It Works](#how-it-works)
5. [Database Schema](#database-schema)
6. [API Reference](#api-reference)
7. [Getting Started](#getting-started)
8. [Deployment](#deployment)
9. [Security](#security)
10. [Testing](#testing)
11. [Project Structure](#project-structure)
12. [License](#license)

---

## Architecture Overview

LabGuardian follows a **three-tier architecture** with real-time capabilities:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                      │
│                                                                              │
│  ┌──────────────────────────┐              ┌────────────────────────────┐   │
│  │  Teacher Dashboard        │              │  Student Machines (N)       │   │
│  │  (React + Vite SPA)       │              │  (Python Agent)             │   │
│  │  - Live monitoring        │              │  - Process monitoring       │   │
│  │  - Session management     │              │  - Device detection         │   │
│  │  - Student analytics      │              │  - Network tracking         │   │
│  └────────┬─────────────────┘              └──────────┬─────────────────┘   │
│           │                                           │                      │
│           │ HTTP/REST + WebSocket                     │ WebSocket             │
└───────────┼───────────────────────────────────────────┼──────────────────────┘
            │                                           │
            ▼                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SERVER LAYER                                      │
│                                                                              │
│  ┌──────────────────────────┐              ┌────────────────────────────┐   │
│  │  HTTP API Server          │              │  WebSocket Server           │   │
│  │  (Express.js - Port 8000) │              │  (ws library - Port 8001)   │   │
│  │                           │              │                              │   │
│  │  - Authentication         │              │  - Agent connections         │   │
│  │  - Session CRUD           │              │  - Teacher subscriptions     │   │
│  │  - Student queries        │              │  - Real-time event forwarding│   │
│  │  - Dashboard stats        │              │  - Redis event buffering     │   │
│  └────────┬──────────────────┘              └──────────┬─────────────────┘   │
│           │                                           │                      │
│           └───────────────────┬───────────────────────┘                      │
│                               │                                              │
│                               ▼                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                        │
│                                                                              │
│  ┌──────────────────────────┐              ┌────────────────────────────┐   │
│  │  PostgreSQL 15            │              │  Redis 7 (Optional)         │   │
│  │  - User data              │              │  - Event buffering          │   │
│  │  - Sessions & students    │              │  - Late-join replay         │   │
│  │  - Live monitoring data   │              │  - 100 events/student       │   │
│  └──────────────────────────┘              └────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

1. **Two-Process Backend**: HTTP and WebSocket servers run as separate Node.js processes, enabling independent scaling and deployment. A WebSocket crash doesn't affect the REST API.

2. **Agent-Based Monitoring**: Lightweight Python agents run on student machines, collecting telemetry and streaming it via WebSocket to the backend.

3. **Real-Time Pub/Sub**: In-memory publisher registry (`wsPublisher.js`) manages teacher subscriptions to student events, with Redis as an optional event buffer.

4. **Idempotent Data Operations**: All live monitoring tables use `INSERT ... ON CONFLICT ... DO UPDATE` patterns, making agent reconnections safe.

5. **Graceful Degradation**: Redis is optional. The system works without it, though teachers joining mid-session won't see buffered historical events.

---

## Tech Stack

### Frontend (Teacher Dashboard)
| Layer | Technology |
|-------|-----------|
| Framework | React 18 with Vite |
| Routing | React Router DOM v7 |
| Styling | Tailwind CSS v3 + Custom Design Tokens |
| Real-Time | WebSocket with automatic reconnection |
| Performance | React Window (virtualized lists) |
| Icons | Lucide React |
| Language | TypeScript (partial) |

### Backend (API + WebSocket Servers)
| Layer | Technology |
|-------|-----------|
| Runtime | Node.js ≥ 18 (ES Modules) |
| HTTP Framework | Express 4 |
| WebSocket | `ws` library (standalone process) |
| Database | PostgreSQL 15 via `pg` (node-postgres) |
| Cache/Buffer | Redis 7 (optional) |
| Authentication | JWT (`jsonwebtoken`) + `bcrypt` |
| Configuration | `dotenv` |
| Testing | Jest + Supertest |
| Dev Tooling | `node --watch` (hot reload) |
| Containerization | Docker Compose |

### Student Agent (Python)
| Layer | Technology |
|-------|-----------|
| Runtime | Python ≥ 3.9 |
| Process Monitoring | `psutil` with classification and incognito detection |
| WebSocket Client | `websockets` |
| HTTP Client | `requests` |
| Network Info | `netifaces` |
| Device Detection | `pyudev` (Linux) with polling fallback (USB only) |
| Terminal Capture | `auditd` (optional, requires root) with system command filtering |
| Browser History | SQLite database scanning (Chrome, Firefox, Edge, Brave) |
| Packaging | setuptools + systemd service |

---

## System Components

### 1. Teacher Dashboard (Frontend)

**Location**: `frontend/`

A modern React SPA that provides teachers with:

- **Authentication**: Secure login with JWT token management
- **Dashboard**: Overview of subjects, sessions, and live session status
- **Subject Management**: Create and manage subjects with department/year info
- **Session Management**: Create, monitor, and end lab sessions
- **Live Student Monitoring**: Real-time tracking with virtualized lists for performance
- **Student Details**: Deep dive into individual student activity:
  - Live process monitoring with WebSocket updates
    - Processes grouped by name with instance counts
    - Incognito/private browsing detection
    - Human-readable process labels
  - Connected USB device tracking
  - Network activity monitoring:
    - **Top Domains Accessed**: Summary of website domains with request counts
    - **Browser History**: Full URLs visited (from Chrome, Firefox, Edge, Brave databases)
    - Domain risk classification (AI cheating tools flagged as high risk)
  - Terminal command logging
    - User commands only (system commands filtered)
    - Risk-level classification for tools (curl, wget, git = high risk)

**Key Features**:
- Responsive design with navy blue college aesthetic
- Persistent live session banner across all pages
- Debounced search (300ms) for filtering students
- Flash highlights for new processes and CPU spikes (>30%)
- Automatic WebSocket reconnection with exponential backoff
- 2-second TTL cache on snapshot endpoints to reduce DB load
- **Process Grouping**: Same-name processes grouped with aggregated stats
- **Browser History Display**: Full URLs with titles, visit counts, and timestamps
- **Connection Status**: Reliable WebSocket status indicator with improved heartbeat (30s timeout)

### 2. Backend API Server

**Location**: `backend/src/server.js`

Express.js HTTP server (Port 8000) handling:

- **Authentication**: Login/logout with JWT generation
- **Subjects**: CRUD operations for teacher's subjects
- **Sessions**: Create, list, view details, and end sessions
- **Students**: Join session, get profile, view devices/network/processes
- **Dashboard**: Aggregated statistics (total subjects, active sessions, etc.)

**Middleware**:
- JWT authentication (`authenticate()`)
- Error handling with structured error responses
- CORS support
- Automatic snake_case → camelCase conversion

### 3. WebSocket Server

**Location**: `backend/src/ws-server.js`

Standalone WebSocket server (Port 8001) managing:

- **Agent Connections**: Student machines connect and stream telemetry
- **Teacher Connections**: Teachers subscribe to student events
- **Heartbeat Monitoring**: 15-second timeout for agent liveness
- **Event Forwarding**: Real-time broadcast from agents to teachers
- **Redis Buffering**: Last 100 events per student for late-joining teachers
- **Browser History Support**: Handles `browser_history` events and forwards to teachers
- **Terminal Event Storage**: Stores terminal commands with risk classification

**Connection Endpoints**:
- Agent: `ws://host:8001/ws/agents/sessions/<sessionId>/students/<studentId>`
- Teacher: `ws://host:8001/ws/teachers/sessions/<sessionId>/students/<rollNo>/processes`

### 4. Student Agent (Lab Guardian)

**Location**: `Lab_guardian/`

Python agent that runs on student lab machines:

**Enhanced Capabilities**:
- **Process Monitoring**: Detects incognito browsing, classifies processes by risk, filters system processes
- **Network Monitoring**: Tracks actual websites visited (not just IPs), filters infrastructure/CDN domains
- **Browser History Scanning**: Reads browser databases for complete URL history
- **Terminal Monitoring**: Captures user commands only, excludes system processes and browser activity
- **USB Detection**: Only tracks external USB storage devices

**Workflow**:
1. **HTTP Join**: `POST /api/students/join-session` with roll number and session ID
2. **Receive JWT**: Short-lived token (1 hour) with student/session info
3. **WebSocket Connect**: Connect to WS server with JWT authentication
4. **Start Monitors**: Run concurrent monitoring tasks
5. **Stream Data**: Send snapshots and deltas at configured intervals
6. **Heartbeat**: Send heartbeat every 5 seconds to stay "online"
7. **Reconnect**: Exponential backoff (1s → 60s max) with jitter on disconnect

**Monitors**:

| Monitor | What It Reports | Snapshot Interval | Delta Interval |
|---------|----------------|-------------------|----------------|
| Process | PIDs, names, CPU %, memory, status (grouped by name in UI) | 30s | 3s |
| Device | USB storage devices only | 30s | 2s (poll) |
| Network | Interfaces, IPs, gateway, DNS, TCP connections | 30s | 5s |
| Network (ss) | Terminal tool connections (curl, wget, git…) | — | 2s |
| Network (auditd) | Full terminal commands with args | — | 2s (tail) |
| Browser History | Full URLs from browser databases (Chrome, Firefox, Edge, Brave) | — | 10s |

**Process Monitoring Features**:
- **System Process Filtering**: Only shows user-started processes, filters out root/system processes
- **Incognito Detection**: Detects Chrome (--incognito), Firefox (--private), Edge (--inprivate) private browsing
- **Process Classification**: 
  - High Risk: Terminals, password crackers, remote access tools
  - Medium Risk (Suspicious): Browsers, IDEs, communication apps, terminals
  - Low Risk: System services (filtered out by default)
- **Resource Thresholds**: Only tracks processes with >0.5% CPU or >30MB memory
- **Process Grouping**: Frontend groups processes with same name, shows instance count and aggregated stats

**Network Monitoring Features**:
- **Domain Tracking**: Monitors connections on web ports (80, 443, 8080, 8443)
- **Infrastructure Filtering**: Filters out CDN/infrastructure domains (1e100.net, cloudfront.net, etc.)
- **Reverse DNS**: Resolves IPs to domain names with fallback to IP if DNS fails
- **Terminal Command Filtering**: Only shows user commands, filters out system commands (cron, systemd)
- **Browser Activity Exclusion**: Terminal section excludes browser network activity

**Browser History Monitoring**:
- **Full URL Tracking**: Reads browser SQLite databases to get complete URLs (not just domains)
- **Supported Browsers**: Google Chrome, Chromium, Mozilla Firefox, Microsoft Edge, Brave
- **Data Extracted**: URL, page title, visit count, last visit timestamp, browser name
- **Safe Reading**: Copies database to /tmp to avoid file locking issues
- **Update Frequency**: Scans every 10 seconds for new URLs

**Message Types** (Agent → Server):
- `process_snapshot`: Full process list
- `process_new`: New process started
- `process_update`: Process stats updated
- `process_end`: Process ended
- `devices_snapshot`: Full device list
- `device_connected`: Device plugged in
- `device_disconnected`: Device removed
- `network_snapshot`: Network info update
- `domain_activity`: Domain connection counts
- `terminal_request`: Terminal tool network activity
- `terminal_command`: Terminal command from auditd
- `browser_history`: Full URLs from browser history
- `heartbeat`: Keep-alive ping

---

## How It Works

### Session Lifecycle

1. **Teacher Creates Session**:
   - Teacher logs into dashboard
   - Creates a session for a subject with batch, lab name, date, and time
   - Session starts with `is_live = true`

2. **Students Join**:
   - Student runs `lab_guardian join` on their machine
   - Agent sends HTTP POST to `/api/students/join-session` with roll number and session ID
   - Backend validates session is live, creates/updates student record
   - Returns JWT token valid for 1 hour

3. **Agent Connects via WebSocket**:
   - Agent connects to WS server with JWT
   - Server validates token, verifies session is live
   - Upserts `session_students` row
   - Sends `ack` with recommended monitoring intervals
   - Starts heartbeat timer (15s timeout)

4. **Real-Time Monitoring**:
   - Agent runs monitors concurrently (process, device, network)
   - Sends snapshots every 30s with full state
   - Sends deltas every 2-5s with incremental changes
   - Server persists all data to PostgreSQL
   - Server forwards events to subscribed teachers in real-time

5. **Teacher Views Live Data**:
   - Teacher opens Student Details page
   - Frontend connects to WS server as teacher
   - Server sends current DB state immediately
   - Server replays up to 100 buffered events from Redis (if available)
   - Teacher receives real-time updates as agent sends them

6. **Session Ends**:
   - Teacher clicks "End Session"
   - Backend sets `is_live = false` and records `end_time`
   - Agents detect session is no longer live and disconnect
   - Teachers receive `agent_offline` events for all students

### Data Flow Example

```
Student Machine (Agent)
    ↓ process_new: {pid: 1234, name: "chrome", cpu: 12.5, memory: 350}
WebSocket Server (Port 8001)
    ↓ 1. Validate message
    ↓ 2. Upsert to live_processes table
    ↓ 3. Buffer in Redis (events:<sessionId>:<studentId>)
    ↓ 4. Publish to wsPublisher
Teacher Dashboard (via WebSocket)
    ← Receives process_new event
    ← Updates UI with flash highlight
```

---

## Database Schema

PostgreSQL 15 with UUIDs and automatic timestamps. All tables use `IF NOT EXISTS` for safe migration reruns.

### Core Tables

**teachers**: Teacher accounts
- `id` (UUID), `email` (unique), `name`, `password_hash`, `role`, `created_at`

**students**: Master student records (identified by roll_no across sessions)
- `id` (UUID), `roll_no` (unique), `name`, `email`, `department`, `year`, `created_at`

**subjects**: Subjects owned by teachers
- `id` (UUID), `teacher_id` (FK), `name`, `department`, `year`, `created_at`

**sessions**: Lab sessions tied to subjects
- `id` (UUID), `subject_id` (FK), `batch`, `lab_name`, `date`, `start_time`, `end_time`, `is_live`, `password`, `created_by` (FK), `created_at`

**session_students**: Junction table tracking student participation
- `id` (UUID), `session_id` (FK), `student_id` (FK), `last_seen_at`, `current_status`, `joined_at`
- Unique constraint: `(session_id, student_id)`

### Monitoring Tables

**connected_devices**: USB and external devices seen during sessions
- `id` (UUID), `session_id` (FK), `student_id` (FK), `device_id`, `device_name`, `device_type` (usb/external), `connected_at`, `disconnected_at`, `metadata` (JSONB), `readable_name`, `risk_level`, `message`
- Unique constraint: `(session_id, student_id, device_id)`
- `disconnected_at IS NULL` means device is currently connected
- **Note**: Currently only tracks USB storage devices (filters out internal drives)

**network_info**: Latest network state per student per session (upserted on change)
- `id` (UUID), `session_id` (FK), `student_id` (FK), `ip_address`, `gateway`, `dns` (JSONB), `active_connections`, `updated_at`
- Unique constraint: `(session_id, student_id)`

**live_processes**: Running snapshot of processes during sessions
- `id` (UUID), `session_id` (FK), `student_id` (FK), `pid`, `process_name`, `cpu_percent`, `memory_mb`, `status` (running/ended), `updated_at`, `risk_level`, `category`, `label`, `is_incognito`
- Unique constraint: `(session_id, student_id, pid)`
- **Enhanced**: Includes process labels (human-readable names), incognito detection flag, and category classification

**domain_activity**: Aggregated domain request counts per student/session
- `id` (UUID), `session_id` (FK), `student_id` (FK), `domain`, `request_count`, `risk_level`, `last_accessed`
- Unique constraint: `(session_id, student_id, domain)`
- **Note**: Only tracks external web ports (80, 443, 8080, 8443), filters infrastructure/CDN domains

**terminal_events**: Commands executed in terminal by students
- `id` (UUID), `session_id` (FK), `student_id` (FK), `tool`, `remote_ip`, `remote_host`, `remote_port`, `pid`, `event_type`, `risk_level`, `message`, `detected_at`
- Captures both network-based terminal tool detection (ss) and auditd command logging
- **Filtered**: Excludes system commands (cron, systemd) and browser network activity

**process_history**: Optional archive for audit/replay (not currently written to)
- Same structure as `live_processes` with `recorded_at` timestamp

### Indexes

| Index | Table | Column(s) | Purpose |
|-------|-------|-----------|---------|
| `idx_students_roll_no` | students | roll_no | Fast lookup by roll number |
| `idx_sessions_is_live` | sessions | is_live | Filter live sessions quickly |
| `idx_session_students_status` | session_students | session_id, current_status | Per-session status queries |
| `idx_live_processes_student` | live_processes | student_id, session_id | Per-student process queries |
| `idx_domain_activity_student` | domain_activity | student_id, session_id | Domain activity queries |
| `idx_terminal_events_student` | terminal_events | student_id, session_id | Terminal command queries |

---

## API Reference

Base URLs:
- HTTP API: `http://localhost:8000/api`
- WebSocket: `ws://localhost:8001`

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | No | Login with email/password, returns JWT |
| POST | `/api/auth/logout` | No | Stateless logout (clears cookie if set) |

### Subjects (Requires Auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/teacher/subjects` | List teacher's subjects with session stats |
| POST | `/api/teacher/subjects` | Create new subject |

### Sessions (Requires Auth)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/teacher/sessions` | Create and start live session |
| GET | `/api/teacher/sessions?status=all|live|ended` | List sessions |
| GET | `/api/teacher/sessions/:sessionId` | Get session details with student count |
| POST | `/api/teacher/sessions/:sessionId/end` | End active session |

### Students & Monitoring

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/students/join-session` | No | Agent joins live session, returns JWT |
| GET | `/api/teacher/sessions/:sessionId/students` | Yes | List students in session |
| GET | `/api/teacher/students/:rollNo` | Yes | Student profile + enrolled subjects |
| GET | `/api/teacher/students/:rollNo/devices?sessionId=...` | Yes | Connected devices |
| GET | `/api/teacher/students/:rollNo/network?sessionId=...` | Yes | Latest network info |
| GET | `/api/teacher/sessions/:sessionId/students/:rollNo/processes` | Yes | Live process snapshot |

### Dashboard (Requires Auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/teacher/dashboard` | Aggregated stats (total subjects, active sessions, total sessions) |

### WebSocket Endpoints

**Agent Connection**:
```
ws://host:8001/ws/agents/sessions/<sessionId>/students/<studentId>?token=<jwt>
```

**Teacher Connection**:
```
ws://host:8001/ws/teachers/sessions/<sessionId>/students/<rollNo>/processes
```

See [System Components](#system-components) section for message types and connection flow.

---

## Getting Started

### Prerequisites

| Dependency | Version | Notes |
|-----------|---------|-------|
| Node.js | ≥ 18 | For backend servers |
| Python | ≥ 3.9 | For student agent |
| PostgreSQL | ≥ 14 | Database |
| Redis | ≥ 7 | Optional but recommended |
| Docker | Latest | For containerized setup |

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd LabGuardian
   ```

2. **Start infrastructure**:
   ```bash
   cd backend
   docker compose up -d
   # Starts Postgres on :5433 and Redis on :6379
   ```

3. **Configure environment**:
   ```bash
   # backend/.env
   PORT=8000
   WS_PORT=8001
   DATABASE_URL=postgres://postgres:password@localhost:5433/lab_monitor
   REDIS_URL=redis://localhost:6379
   JWT_SECRET=your-secure-secret-key
   JWT_EXPIRES_IN=8h
   ```

   ```bash
   # frontend/.env
   VITE_API_BASE=http://localhost:8000/api
   VITE_WS_BASE=ws://localhost:8001
   ```

4. **Install dependencies and run migrations**:
   ```bash
   cd backend
   npm install
   npm run migrate
   ```

5. **Seed test data** (optional):
   ```bash
   node tests/e2e/seed.js
   ```

6. **Start backend servers**:
   ```bash
   # Terminal 1 - HTTP API
   npm run dev  # Port 8000

   # Terminal 2 - WebSocket Server
   npm run dev:ws  # Port 8001
   ```

7. **Start frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

8. **Install student agent**:
   ```bash
   cd Lab_guardian
   sudo bash setup.sh  # With auditd rules
   # OR
   bash setup.sh --no-auditd  # Without auditd
   ```

### Option 2: Manual Setup

1. **Install PostgreSQL and Redis** locally
2. **Create database**: `createdb lab_monitor`
3. **Update DATABASE_URL** in `backend/.env` to use port 5432
4. Follow steps 4-8 from Docker setup above

### Quick Test

1. Login with test credentials (from seed data)
2. Create a subject
3. Create a session
4. Run `lab_guardian join` on a student machine
5. Watch real-time data appear in the teacher dashboard

---

## Deployment

### Backend Production Setup

```bash
# Build and start HTTP server
npm start  # node src/server.js

# Start WebSocket server
npm run ws  # node src/ws-server.js
```

### Frontend Production Build

```bash
cd frontend
npm run build
# Serve dist/ with nginx, Apache, or any static file server
```

### Student Agent Deployment

**Systemd Service**:
```bash
sudo cp Lab_guardian/systemd/lab_guardian.service /etc/systemd/system/
sudo mkdir -p /etc/lab_guardian
echo -e "ROLL_NO=CS2021001\nSESSION_ID=<uuid>" | sudo tee /etc/lab_guardian/env
sudo systemctl enable --now lab_guardian
```

**Debian Package**:
```bash
cd Lab_guardian
dpkg-deb --build lab_guardian lab-guardian_1.0.0_all.deb
sudo dpkg -i lab-guardian_1.0.0_all.deb
```

### Environment Variables

#### Backend (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8000 | HTTP server port |
| `WS_PORT` | 8001 | WebSocket server port |
| `DATABASE_URL` | - | PostgreSQL connection string |
| `REDIS_URL` | redis://localhost:6379 | Redis connection string (optional) |
| `JWT_SECRET` | - | JWT signing secret (REQUIRED) |
| `JWT_EXPIRES_IN` | 8h | JWT token expiry |
| `LOG_LEVEL` | info | Log level (debug|info|warn|error) |

#### Frontend (`.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE` | Backend HTTP API base URL |
| `VITE_WS_BASE` | Backend WebSocket base URL |

#### Student Agent (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `LAB_GUARDIAN_API_URL` | http://localhost:8000 | Backend HTTP base URL |
| `LAB_GUARDIAN_WS_URL` | ws://localhost:8001 | Backend WS base URL |
| `LG_SNAPSHOT_INTERVAL` | 30 | Full snapshot interval (sec) |
| `LG_DELTA_INTERVAL` | 3 | Process delta interval (sec) |
| `LG_DEVICE_POLL_INTERVAL` | 2 | Device poll interval (sec) |
| `LG_NETWORK_POLL_INTERVAL` | 5 | Legacy network poll interval |
| `LG_NETWORK_SS_INTERVAL` | 2 | ss connection poll interval |
| `LG_AUDITD_LOG_PATH` | /var/log/audit/audit.log | auditd log file path |
| `LG_HEARTBEAT_INTERVAL` | 5 | Heartbeat send interval (sec) |

### Scheduled Cleanup

Run daily to delete monitoring data older than 7 days:

```bash
0 3 * * * cd /path/to/backend && node src/scripts/cleanup.js
```

Or manually:
```bash
cd backend
npm run cleanup
```

---

## Security

### Authentication & Authorization

- **JWT-based authentication** for both HTTP and WebSocket connections
- **Role-based access control**: `teacher` and `student` roles
- **Token-path matching**: Agent JWTs must match sessionId/studentId in URL
- **Session ownership validation**: Teachers can only access their own sessions
- **Short-lived agent tokens**: 1-hour expiry for student JWTs

### Data Protection

- **Parameterized SQL queries** throughout (no ORM, zero SQL injection risk)
- **Snake_case → camelCase conversion** happens at API boundary only
- **Metadata sanitization**: Device metadata capped at 4 KB per message
- **Rate limiting**: Max 2 process updates/sec per student (excess silently dropped)
- **Message validation**: Unknown message types or missing data rejected

### Network Security

- **HTTPS/WSS recommended** for production (frontend enforces secure connections)
- **CORS configured** on backend
- **Stateless JWT**: No session data stored server-side
- **Graceful error handling**: 5xx errors return generic messages, no stack traces exposed

### Known Issues

> **Security Note**: `authController.js` currently performs plain-text password comparison. Use `bcrypt.compare()` before deploying to production (bcrypt is already a dependency).

---

## Testing

### Backend Tests

```bash
cd backend

# Unit tests (Jest)
npm test

# E2E flow test (requires running servers + seeded data)
npm run test:e2e

# Manual WebSocket agent simulation
TOKEN=<jwt> SESSION_ID=<uuid> STUDENT_ID=<uuid> node tests/e2e/ws-agent-test.js
```

### Test Files

| File | Purpose |
|------|---------|
| `tests/unit/auth.test.js` | Authentication logic |
| `tests/unit/dashboard.test.js` | Dashboard statistics |
| `tests/unit/cache.test.js` | TTL cache utility |
| `tests/unit/joinSession.test.js` | Student join flow |
| `tests/e2e/flow.test.js` | Full API flow test |
| `tests/e2e/ws-agent-test.js` | WebSocket agent simulator |
| `tests/e2e/seed.js` | Test data seeding |

### Manual Testing

1. **Login**:
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"teacher@example.com","password":"secret"}'
   ```

2. **Create Session**:
   ```bash
   curl -X POST http://localhost:8000/api/teacher/sessions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <TOKEN>" \
     -d '{"subjectId":"<UUID>","batch":"A","lab":"Lab-101","date":"2026-03-04","startTime":"09:00"}'
   ```

3. **Join Session (Agent)**:
   ```bash
   curl -X POST http://localhost:8000/api/students/join-session \
     -H "Content-Type: application/json" \
     -d '{"rollNo":"CS2021001","sessionId":"<SESSION_ID>"}'
   ```

---

## Project Structure

```
LabGuardian/
├── frontend/                      # Teacher Dashboard (React + Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/           # Sidebar, Topbar, LiveSessionBanner
│   │   │   ├── ui/               # Button, Card, Modal, InputField, etc.
│   │   │   └── session/          # StudentListItem
│   │   ├── pages/                # Login, Dashboard, MySubjects, CreateSession,
│   │   │                         # MySessions, LiveSession, StudentDetails
│   │   ├── services/             # api.js (HTTP), socket.js (WebSocket)
│   │   ├── context/              # SessionContext.jsx
│   │   ├── styles/               # tokens.css (design system)
│   │   ├── App.jsx               # Main app with routing
│   │   └── routes.jsx            # Route definitions
│   ├── .env                      # Environment variables
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                       # API + WebSocket Servers (Node.js)
│   ├── src/
│   │   ├── app.js                # Express app setup
│   │   ├── server.js             # HTTP server entry (Port 8000)
│   │   ├── ws-server.js          # WebSocket server entry (Port 8001)
│   │   ├── config/               # Environment config + Redis client
│   │   ├── db/
│   │   │   ├── index.js          # Postgres pool + query helper
│   │   │   └── migrations/       # SQL migration files
│   │   ├── routes/               # Express route definitions
│   │   ├── controllers/          # Request handlers
│   │   ├── services/             # Business logic (process, device, session, student, wsPublisher)
│   │   ├── middleware/           # Auth, error handling
│   │   ├── utils/                # Helpers, cache utility
│   │   └── scripts/              # migrate.js, cleanup.js
│   ├── tests/                    # Unit and E2E tests
│   ├── docker-compose.yml        # Postgres + Redis containers
│   └── package.json
│
├── Lab_guardian/                  # Student Agent (Python)
│   ├── lab_guardian/
│   │   ├── cli.py                # Command-line entry point
│   │   ├── config.py             # Environment-based defaults
│   │   ├── api.py                # HTTP join-session client
│   │   ├── ws_client.py          # WebSocket + reconnect + heartbeat
│   │   ├── dispatcher.py         # Orchestrates monitors → ws_client
│   │   └── monitor/
│   │       ├── process_monitor.py    # psutil-based process tracking
│   │       ├── device_monitor.py     # USB/block device monitoring
│   │       └── network_monitor.py    # ss + auditd + domain aggregation
│   ├── systemd/                  # systemd service file
│   ├── debian/                   # Debian package configuration
│   ├── setup.py                  # Python package setup
│   ├── setup.sh                  # Dependency installer + auditd rules
│   └── requirements.txt
│
├── dev/                          # Development utilities
│   ├── agent-docker/             # Dockerfile for agent testing
│   └── tests/                    # Integration tests
│
└── .gitignore
```

---

## Design Decisions & Best Practices

### Why Two Backend Processes?

Separating HTTP and WebSocket servers provides:
- **Independent scaling**: Scale WS servers based on agent count, HTTP servers based on API traffic
- **Fault isolation**: WS crash doesn't affect REST API availability
- **Different resource needs**: WS server is stateful (in-memory maps), HTTP server is stateless
- **Easier deployment**: Can deploy updates to one without affecting the other

### Why No ORM?

Raw parameterized SQL via `node-postgres` offers:
- **Full query visibility**: No hidden N+1 queries or unexpected behavior
- **Zero overhead**: No ORM abstraction layer
- **Complete control**: Complex JOINs, UPSERTs, and window functions without fighting the ORM
- **Better performance**: Direct SQL execution with connection pooling

### Upsert Pattern for Idempotency

All live monitoring tables use:
```sql
INSERT INTO live_processes (...) VALUES (...)
ON CONFLICT (session_id, student_id, pid) DO UPDATE SET ...
```

This makes agent messages **idempotent** - reconnecting agents can resend full snapshots without creating duplicates.

### Redis as Optional Enhancement

The system is designed to work **without Redis**:
- Core features (real-time streaming, DB persistence) always work
- Redis only enhances late-join experience (event replay)
- Graceful degradation: Redis connection failure doesn't crash the server

### Database Connection Pool

- **Max connections**: 20
- **Idle timeout**: 30 seconds
- **Connection timeout**: 5 seconds
- **Slow query logging**: Queries >500ms logged as warnings

### Graceful Shutdown

Both servers handle `SIGINT`/`SIGTERM`:
1. Close HTTP/WS server (stop accepting new connections)
2. Close Redis connection
3. Drain Postgres pool
4. Exit cleanly

---

## Performance Optimizations

### Frontend
- **Virtualized lists**: React Window renders only visible student rows
- **Debounced search**: 300ms delay before filtering
- **Memoized components**: Prevent unnecessary re-renders
- **Code splitting**: Route-based lazy loading potential
- **2-second TTL cache**: Snapshot endpoints cache DB responses

### Backend
- **Connection pooling**: Reuse Postgres connections
- **In-memory pub/sub**: Zero-latency event forwarding to teachers
- **Redis buffering**: O(1) event append with LTRIM for cap
- **Rate limiting**: Drop excess process updates (>2/sec/student)
- **Per-message deflate**: WebSocket compression enabled

### Agent
- **Delta updates**: Send only changed processes, not full list
- **Concurrent monitors**: Async I/O for all monitoring tasks
- **Exponential backoff**: Smart reconnection (1s → 60s max with jitter)
- **Efficient polling**: Use `ss` command instead of full network scans

---

## Monitoring & Maintenance

### Health Checks

```bash
# Backend HTTP health
curl http://localhost:8000/health
# Returns: {"status":"ok"}
```

### Log Levels

Set `LOG_LEVEL` environment variable:
- `debug`: Verbose logging for development
- `info`: Standard operational logs
- `warn`: Warnings and potential issues
- `error`: Errors only

### Database Maintenance

**Cleanup old data** (7+ days):
```bash
cd backend
npm run cleanup
```

**Re-run migrations** (safe):
```bash
npm run migrate
```

### Agent Management

**Check agent status**:
```bash
sudo systemctl status lab_guardian
```

**View agent logs**:
```bash
journalctl -u lab_guardian -f
```

**Restart agent**:
```bash
sudo systemctl restart lab_guardian
```

---

## Troubleshooting

### Common Issues

**Agent won't connect**:
- Verify session is live (`is_live = true`)
- Check JWT hasn't expired (1-hour limit)
- Ensure `ROLL_NO` and `SESSION_ID` are correct in agent config
- Check network connectivity to backend ports (8000, 8001)

**Teacher not receiving real-time updates**:
- Verify WebSocket connection is established (check browser dev tools)
- Confirm teacher owns the session
- Check Redis is running (if using event buffering)
- Look for rate limiting in server logs

**Database connection errors**:
- Verify `DATABASE_URL` in `.env`
- Check Postgres is running and accessible
- Ensure database exists (`createdb lab_monitor`)
- Run migrations: `npm run migrate`

**High memory usage**:
- Check for memory leaks in long-running sessions
- Monitor Postgres connection pool usage
- Verify Redis memory usage (`redis-cli INFO memory`)
- Run cleanup script to remove old data

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow existing code style and conventions
- Write tests for new features
- Update documentation for API changes
- Use meaningful commit messages
- Ensure all tests pass before submitting PR

---

## License

MIT License - See individual component READMEs for details.

---

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation in component READMEs
- Review test files for usage examples

---

**Built with ❤️ for better lab monitoring**
