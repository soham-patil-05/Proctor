# Lab Insight — Backend

A Node.js backend for **real-time lab session monitoring**. It lets teachers create lab sessions,
and student-side agents stream live telemetry (processes, devices, network) directly to the
teacher's dashboard over WebSockets.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture Overview](#architecture-overview)
3. [Folder Structure](#folder-structure)
4. [Environment Variables](#environment-variables)
5. [Getting Started](#getting-started)
6. [Database](#database)
   - [Table: teachers](#table-teachers)
   - [Table: students](#table-students)
   - [Table: subjects](#table-subjects)
   - [Table: sessions](#table-sessions)       
   - [Table: session\_students](#table-session_students)
   - [Table: connected\_devices](#table-connected_devices)
   - [Table: network\_info](#table-network_info)
   - [Table: live\_processes](#table-live_processes)
   - [Table: process\_history](#table-process_history)
   - [Indexes](#indexes)
7. [REST API Reference](#rest-api-reference)
   - [Health Check](#health-check)
   - [Auth](#auth)
   - [Subjects](#subjects)
   - [Sessions](#sessions)
   - [Students & Monitoring](#students--monitoring)
   - [Dashboard](#dashboard)
8. [WebSocket Server](#websocket-server)
   - [Agent Connection](#agent-connection)
   - [Teacher Connection](#teacher-connection)
   - [Agent → Server Message Types](#agent--server-message-types)               
   - [Server → Teacher Push Types](#server--teacher-push-types)
   - [Heartbeat & Liveness](#heartbeat--liveness)
   - [Redis Event Buffer](#redis-event-buffer)
9. [Services Layer](#services-layer)
10. [Middleware](#middleware)
11. [Utilities](#utilities)
12. [Scripts](#scripts)
13. [Docker Compose](#docker-compose)
14. [Running Tests](#running-tests)
15. [Design Notes & Decisions](#design-notes--decisions)

---

## Tech Stack

| Layer          | Technology                        |
|----------------|-----------------------------------|
| Runtime        | Node.js (ES Modules, `"type":"module"`) |
| HTTP Server    | Express 4                         |
| WebSocket      | `ws` library (standalone process) |
| Database       | PostgreSQL 15 via `pg` (node-postgres) |
| Cache / Buffer | Redis 7 (optional — falls back gracefully) |
| Auth           | JWT (`jsonwebtoken`) + `bcrypt`   |
| Config         | `dotenv`                          |
| Testing        | Jest + Supertest                  |
| Dev tooling    | `node --watch` (no extra bundler) |
| Containerisation | Docker Compose                  |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT SIDE                             │
│  Teacher Browser (React)          Student Agent (Python script) │
│  - REST calls via api.js          - WS connects as 'agent'      │
│  - WS connects as 'teacher'       - streams process/device data │
└───────────┬──────────────────────────────────┬──────────────────┘
            │ HTTP/REST                         │ WebSocket
            ▼                                   ▼
┌───────────────────────┐             ┌──────────────────────────┐
│   Express HTTP Server  │             │  WebSocket Server         │
│   src/server.js        │             │  src/ws-server.js         │
│   PORT 8000 (default)  │             │  PORT 8001 (default)      │
│                        │             │                           │
│  /api/auth/*           │             │  /ws/agents/...  (agent)  │
│  /api/teacher/*        │             │  /ws/teachers/.. (teacher)│
└──────────┬────────────┘             └──────────┬───────────────┘
           │                                      │
           └──────────────┬───────────────────────┘
                          ▼
              ┌──────────────────────┐
              │   PostgreSQL DB       │
              │   + Redis (optional)  │
              └──────────────────────┘
```

The HTTP server and the WebSocket server are **two separate Node.js processes** that both connect
to the same PostgreSQL database. Redis is used by the WS server to buffer the last 100 events per
student for teachers who connect late.

---

## Folder Structure

```
backend/
├── docker-compose.yml          # Postgres + Redis containers
├── package.json
├── src/
│   ├── app.js                  # Express app setup (middleware + routes)
│   ├── server.js               # Starts HTTP server, graceful shutdown
│   ├── ws-server.js            # Standalone WebSocket server
│   │
│   ├── config/
│   │   └── index.js            # Centralised env config + Redis singleton
│   │
│   ├── db/
│   │   ├── index.js            # pg Pool, query() helper, getClient()
│   │   └── migrations/
│   │       └── 001_create_tables.sql   # Full schema DDL
│   │
│   ├── routes/
│   │   ├── auth.js             # POST /login, POST /logout
│   │   ├── subjects.js         # GET /, POST /
│   │   ├── sessions.js         # CRUD + end
│   │   ├── students.js         # Session students, profile, devices, network, processes
│   │   └── dashboard.js        # Aggregated stats
│   │
│   ├── controllers/
│   │   ├── authController.js
│   │   ├── subjectsController.js
│   │   ├── sessionsController.js
│   │   ├── studentsController.js
│   │   └── dashboardController.js
│   │
│   ├── services/
│   │   ├── processService.js   # live_processes DB operations
│   │   ├── deviceService.js    # connected_devices + network_info DB operations
│   │   ├── sessionService.js   # session/student DB helpers (used by WS server)
│   │   └── wsPublisher.js      # In-memory teacher WS subscription registry
│   │
│   ├── middleware/
│   │   ├── auth.js             # JWT authenticate() + verifyToken()
│   │   └── errorHandler.js     # Central Express error handler
│   │
│   ├── utils/
│   │   └── helpers.js          # asyncHandler, httpError, toCamel, rowsToCamel, pick
│   │
│   └── scripts/
│       ├── migrate.js          # Runs all SQL files in db/migrations/
│       └── cleanup.js          # Deletes rows older than 7 days
│
└── tests/
    ├── unit/
    │   ├── auth.test.js
    │   └── dashboard.test.js
    └── e2e/
        ├── flow.test.js
        ├── seed.js
        └── ws-agent-test.js
```

---

## Environment Variables

Create a `.env` file at `backend/.env`:

```env
# HTTP server
PORT=8000

# WebSocket server
WS_PORT=8001

# PostgreSQL connection string
DATABASE_URL=postgres://postgres:password@localhost:5432/lab_monitor

# Redis (optional — falls back to in-memory if unavailable)
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=replace_with_secure_secret
JWT_EXPIRES_IN=8h
```

All variables are loaded via `dotenv` and exposed through `src/config/index.js`.
Defaults are provided for every variable so the server can start without a `.env` in development.

---

## Getting Started

### Prerequisites

| Dependency | Version |
|------------|---------|
| Node.js    | ≥ 18    |
| PostgreSQL | ≥ 14    |
| Redis      | ≥ 7 (optional but recommended) |

### 1. Install dependencies

```bash
cd backend
npm install
```

### 2. Start infrastructure

```bash
docker compose up -d       # starts Postgres on :5433 and Redis on :6379
```

### 3. Run migrations

```bash
npm run migrate            # executes 001_create_tables.sql against DATABASE_URL
```

### 4. Seed test data (optional)

```bash
node tests/e2e/seed.js
```

### 5. Start servers

```bash
# Terminal 1 — REST API
npm run dev                # node --watch src/server.js  → :8000

# Terminal 2 — WebSocket server
npm run dev:ws             # node --watch src/ws-server.js → :8001
```

### Production

```bash
npm start                  # node src/server.js
npm run ws                 # node src/ws-server.js
```

---

## Database

PostgreSQL 15. Extensions `uuid-ossp` (UUID generation) and `pgcrypto` are enabled.
All UUIDs are auto-generated with `uuid_generate_v4()`. All timestamps use `timestamptz`.

### Table: `teachers`

Stores teacher accounts. Each teacher logs in and manages their own subjects and sessions.

| Column          | Type        | Constraints                     | Notes                          |
|-----------------|-------------|----------------------------------|--------------------------------|
| `id`            | UUID        | PK, default `uuid_generate_v4()`|                                |
| `email`         | TEXT        | UNIQUE, NOT NULL                 | Login identifier               |
| `name`          | TEXT        | NOT NULL                         |                                |
| `password_hash` | TEXT        | NOT NULL                         | Stored credential (see Design Notes) |
| `role`          | TEXT        | NOT NULL, default `'teacher'`    | Reserved for future role expansion |
| `created_at`    | timestamptz | NOT NULL, default `now()`        |                                |

---

### Table: `students`

Master student records. Students are identified by their `roll_no` across all sessions.

| Column       | Type        | Constraints                     | Notes                          |
|--------------|-------------|----------------------------------|--------------------------------|
| `id`         | UUID        | PK                               |                                |
| `roll_no`    | TEXT        | UNIQUE, NOT NULL                 | Primary lookup key             |
| `name`       | TEXT        | NOT NULL                         |                                |
| `email`      | TEXT        |                                  | Optional                       |
| `department` | TEXT        |                                  |                                |
| `year`       | INT         |                                  |                                |
| `created_at` | timestamptz | NOT NULL, default `now()`        |                                |

---

### Table: `subjects`

A subject belongs to one teacher. A teacher can have many subjects.

| Column       | Type        | Constraints                                    | Notes      |
|--------------|-------------|------------------------------------------------|------------|
| `id`         | UUID        | PK                                             |            |
| `teacher_id` | UUID        | NOT NULL, FK → `teachers(id)` ON DELETE CASCADE|            |
| `name`       | TEXT        | NOT NULL                                       |            |
| `department` | TEXT        |                                                | Optional   |
| `year`       | INT         |                                                | Optional   |
| `created_at` | timestamptz | NOT NULL, default `now()`                      |            |

---

### Table: `sessions`

A lab session ties a subject to a physical lab on a specific date.
`is_live = true` while the session is active; set to `false` when the teacher ends it.

| Column       | Type        | Constraints                                    | Notes                                   |
|--------------|-------------|------------------------------------------------|-----------------------------------------|
| `id`         | UUID        | PK                                             |                                         |
| `subject_id` | UUID        | NOT NULL, FK → `subjects(id)` ON DELETE CASCADE|                                         |
| `batch`      | TEXT        | NOT NULL                                       | e.g. `"A"`, `"2025-Sem2"`              |
| `lab_name`   | TEXT        | NOT NULL                                       | e.g. `"Lab 101"`                        |
| `date`       | date        | NOT NULL                                       |                                         |
| `start_time` | time        | NOT NULL                                       |                                         |
| `end_time`   | timestamptz |                                                | Set when session is ended               |
| `is_live`    | boolean     | NOT NULL, default `false`                      | `true` while session is active          |
| `password`   | TEXT        |                                                | Optional — agents may use this to join  |
| `created_by` | UUID        | NOT NULL, FK → `teachers(id)`                  |                                         |
| `created_at` | timestamptz | NOT NULL, default `now()`                      |                                         |

---

### Table: `session_students`

Junction table: tracks which students have connected to which session.
Updated in real-time as agents connect and send heartbeats.

| Column           | Type        | Constraints                                       | Notes                                |
|------------------|-------------|---------------------------------------------------|--------------------------------------|
| `id`             | UUID        | PK                                                |                                      |
| `session_id`     | UUID        | NOT NULL, FK → `sessions(id)` ON DELETE CASCADE   |                                      |
| `student_id`     | UUID        | NOT NULL, FK → `students(id)` ON DELETE CASCADE   |                                      |
| `last_seen_at`   | timestamptz |                                                   | Updated on every message / heartbeat |
| `current_status` | TEXT        | default `'normal'`                                | e.g. `'normal'`, `'flagged'`         |
| `joined_at`      | timestamptz | default `now()`                                   |                                      |
|                  |             | UNIQUE(`session_id`, `student_id`)                |                                      |

---

### Table: `connected_devices`

Records USB and external devices seen during a session.
`disconnected_at IS NULL` means the device is currently connected.

| Column            | Type        | Constraints                                              | Notes                       |
|-------------------|-------------|----------------------------------------------------------|-----------------------------|
| `id`              | UUID        | PK                                                       |                             |
| `session_id`      | UUID        | NOT NULL, FK → `sessions(id)` ON DELETE CASCADE          |                             |
| `student_id`      | UUID        | NOT NULL, FK → `students(id)` ON DELETE CASCADE          |                             |
| `device_id`       | TEXT        |                                                          | OS-level device identifier  |
| `device_name`     | TEXT        | NOT NULL                                                 |                             |
| `device_type`     | TEXT        | NOT NULL, CHECK IN (`'usb'`, `'external'`)               |                             |
| `connected_at`    | timestamptz | NOT NULL, default `now()`                                |                             |
| `disconnected_at` | timestamptz |                                                          | NULL = still connected       |
| `metadata`        | JSONB       |                                                          | Arbitrary extra info         |
|                   |             | UNIQUE(`session_id`, `student_id`, `device_id`)          |                             |

---

### Table: `network_info`

Latest network state per student per session (one row per pair — upserted on change).

| Column               | Type        | Constraints                                     | Notes                      |
|----------------------|-------------|------------------------------------------------|----------------------------|
| `id`                 | UUID        | PK                                             |                            |
| `session_id`         | UUID        | NOT NULL, FK → `sessions(id)` ON DELETE CASCADE|                            |
| `student_id`         | UUID        | NOT NULL, FK → `students(id)` ON DELETE CASCADE|                            |
| `ip_address`         | TEXT        |                                                |                            |
| `gateway`            | TEXT        |                                                |                            |
| `dns`                | JSONB       |                                                | Array of DNS server strings |
| `active_connections` | INT         |                                                | Number of open connections  |
| `updated_at`         | timestamptz | NOT NULL, default `now()`                      |                            |
|                      |             | UNIQUE(`session_id`, `student_id`)             |                            |

---

### Table: `live_processes`

Running snapshot of processes for each student during a session.
One row per `(session_id, student_id, pid)` — upserted on every update.

| Column         | Type          | Constraints                                         | Notes                |
|----------------|---------------|-----------------------------------------------------|----------------------|
| `id`           | UUID          | PK                                                  |                      |
| `session_id`   | UUID          | NOT NULL, FK → `sessions(id)` ON DELETE CASCADE     |                      |
| `student_id`   | UUID          | NOT NULL, FK → `students(id)` ON DELETE CASCADE     |                      |
| `pid`          | INT           | NOT NULL                                            | OS process ID        |
| `process_name` | TEXT          | NOT NULL                                            |                      |
| `cpu_percent`  | NUMERIC(5,2)  | default `0`                                         |                      |
| `memory_mb`    | NUMERIC(10,2) | default `0`                                         |                      |
| `status`       | TEXT          | NOT NULL, CHECK IN (`'running'`, `'ended'`)         |                      |
| `updated_at`   | timestamptz   | NOT NULL, default `now()`                           |                      |
|                |               | UNIQUE(`session_id`, `student_id`, `pid`)           |                      |

---

### Table: `process_history`

Optional archive — not currently written to by the main code, but the schema is created for
future audit/replay use.

| Column         | Type          | Notes                  |
|----------------|---------------|------------------------|
| `id`           | UUID          | PK                     |
| `session_id`   | UUID          |                        |
| `student_id`   | UUID          |                        |
| `pid`          | INT           |                        |
| `process_name` | TEXT          |                        |
| `cpu_percent`  | NUMERIC(5,2)  |                        |
| `memory_mb`    | NUMERIC(10,2) |                        |
| `status`       | TEXT          |                        |
| `recorded_at`  | timestamptz   | default `now()`        |

---

### Indexes

| Index                          | Table              | Column(s)                      | Purpose                              |
|--------------------------------|--------------------|--------------------------------|--------------------------------------|
| `idx_students_roll_no`         | `students`         | `roll_no`                      | Fast lookup by roll number           |
| `idx_sessions_is_live`         | `sessions`         | `is_live`                      | Filter live sessions quickly         |
| `idx_session_students_status`  | `session_students` | `session_id`, `current_status` | Per-session status queries           |
| `idx_live_processes_student`   | `live_processes`   | `student_id`, `session_id`     | Per-student process queries          |

---

## REST API Reference

Base URL: `http://localhost:8000/api`

All protected routes require:
```
Authorization: Bearer <JWT>
```

---

### Health Check

| Method | Path       | Auth | Description             |
|--------|------------|------|-------------------------|
| GET    | `/health`  | No   | Returns `{"status":"ok"}` |

---

### Auth

Mounted at `/api/auth`

#### `POST /api/auth/login`

**Request body**
```json
{ "email": "teacher@example.com", "password": "secret" }
```

**Response `200`**
```json
{
  "token": "<JWT>",
  "name": "Dr. Smith",
  "role": "teacher",
  "teacherId": "<uuid>"
}
```

**Errors:** `400` missing fields · `401` invalid credentials

---

#### `POST /api/auth/logout`

Stateless logout — clears the `token` cookie if set.

**Response `200`:** `{ "message": "Logged out" }`

---

### Subjects

Mounted at `/api/teacher/subjects` — **all routes require auth**

#### `GET /api/teacher/subjects`

List all subjects for the authenticated teacher, with session stats.

**Response `200`**
```json
[
  {
    "id": "<uuid>",
    "name": "Operating Systems",
    "department": "CSE",
    "year": 2,
    "createdAt": "2025-01-10T10:00:00Z",
    "totalSessions": 5,
    "active": true
  }
]
```

The `active` flag is `true` if at least one session for this subject is currently `is_live = true`.

---

#### `POST /api/teacher/subjects`

**Request body**
```json
{ "name": "Data Structures", "department": "CSE", "year": 1 }
```

**Response `201`** — created subject object  
**Errors:** `400` — `name` is required

---

### Sessions

Mounted at `/api/teacher/sessions` — **all routes require auth**

#### `POST /api/teacher/sessions`

Create and immediately start a new lab session (`is_live = true`).

**Request body**
```json
{
  "subjectId": "<uuid>",
  "batch": "A",
  "lab": "Lab 101",
  "date": "2025-03-04",
  "startTime": "09:00",
  "password": "optional-join-password"
}
```

**Response `201`**
```json
{
  "sessionId": "<uuid>",
  "isLive": true,
  "joinUrl": "/ws/agents/sessions/<sessionId>/students/:studentId"
}
```

**Errors:** `400` missing fields · `403` subject not owned by teacher

---

#### `GET /api/teacher/sessions?status=all|live|ended`

List sessions for the authenticated teacher, joined with `subject_name`.

| `status` value | Filter applied             |
|----------------|----------------------------|
| `all` (default)| no filter                  |
| `live`         | `is_live = true`           |
| `ended`        | `is_live = false`          |

**Response `200`** — array of session objects (camelCase), newest first.

---

#### `GET /api/teacher/sessions/:sessionId`

Get full session details including `studentCount`. Only accessible by the owning teacher.

**Response `200`** — session object with `studentCount` (integer).  
**Errors:** `404` not found or not owned.

---

#### `POST /api/teacher/sessions/:sessionId/end`

End an active session → sets `is_live = false` and `end_time = now()`.

**Response `200`**
```json
{ "status": "ended", "endedAt": "2025-03-04T11:30:00Z" }
```

**Errors:** `404` session not found or not owned.

---

### Student Agent — Join Session (Public)

Mounted at `/api/students` — **no auth required**.

#### `POST /api/students/join-session`

Called by the Python agent to register a student in a live session and receive a JWT.

**Request Body**
```json
{
  "rollNo": "CS2021001",
  "sessionId": "<uuid>",
  "password": "optional-session-password"
}
```

**Response `200`**
```json
{
  "token": "<jwt>",
  "studentId": "<uuid>",
  "sessionId": "<uuid>",
  "expiresIn": "1h"
}
```

The returned JWT carries `{ studentId, rollNo, sessionId, role: "student" }` and is used for
the WebSocket agent connection. It expires in 1 hour.

**Errors:**
- `400` missing `rollNo` or `sessionId`
- `404` session not found
- `403` session not live, or incorrect password

---

### Students & Monitoring

Mounted at `/api/teacher` — **all routes require auth**

#### `GET /api/teacher/sessions/:sessionId/students`

List all students who have connected to the session.

**Response `200`**
```json
[
  {
    "rollNo": "CS2021001",
    "name": "Alice",
    "status": "normal",
    "lastSeen": "2025-03-04T10:15:30Z"
  }
]
```

**Errors:** `404` session not found or not owned.

---

#### `GET /api/teacher/sessions/:sessionId/students/:rollNo/processes`

Get the live process snapshot from `live_processes` for a student in a session.

**Response `200`**
```json
[
  {
    "pid": 1234,
    "processName": "chrome.exe",
    "cpuPercent": "12.50",
    "memoryMb": "350.00",
    "status": "running",
    "updatedAt": "2025-03-04T10:16:00Z"
  }
]
```

---

#### `GET /api/teacher/students/:rollNo`

Get a student's profile plus all subjects they've been enrolled in across sessions.

**Response `200`**
```json
{
  "id": "<uuid>",
  "rollNo": "CS2021001",
  "name": "Alice",
  "email": "alice@example.com",
  "department": "CSE",
  "year": 3,
  "createdAt": "...",
  "enrolledSubjects": [
    { "id": "<uuid>", "name": "OS", "department": "CSE", "year": 3 }
  ]
}
```

**Errors:** `404` student not found.

---

#### `GET /api/teacher/students/:rollNo/devices?sessionId=<uuid>`

Get currently-connected devices (where `disconnected_at IS NULL`).  
`sessionId` query param is **required**.S

**Response `200`**
```json
{
  "usb": [
    { "deviceId": "USB001", "deviceName": "SanDisk USB", "connectedAt": "...", "metadata": null }
  ],
  "external": []
}
```

**Errors:** `400` missing sessionId · `404` student not found.

---

#### `GET /api/teacher/students/:rollNo/network?sessionId=<uuid>`

Get the latest network snapshot for a student.  
`sessionId` query param is **required**.

**Response `200`**
```json
{
  "ipAddress": "192.168.1.105",
  "gateway": "192.168.1.1",
  "dns": ["8.8.8.8", "8.8.4.4"],
  "activeConnections": 12,
  "updatedAt": "2025-03-04T10:17:00Z"
}
```

Returns `null` if no data has been received yet.  
**Errors:** `400` missing sessionId · `404` student not found.

---

### Dashboard

Mounted at `/api/teacher/dashboard` — **requires auth**

#### `GET /api/teacher/dashboard`

**Response `200`**
```json
{
  "totalSubjects": 4,
  "activeSession": 1,
  "totalSessions": 12
}
```

---

## WebSocket Server

Runs as an **independent Node.js process** on `WS_PORT` (default **8001**).  
Two connection roles: **agent** (student machine) and **teacher** (dashboard).

Auth uses **role-based JWT** validation:
- **Agent** tokens must have `role === "student"` (issued by `POST /api/students/join-session`)
- **Teacher** tokens must have `role === "teacher"` (issued by `POST /api/auth/login`)

Token is passed as:
- `Authorization: Bearer <token>` header on the upgrade request, **or**
- `?token=<token>` query parameter

**Enhancements in v2:**
- **Token-path matching** — agent JWTs must match the `sessionId`/`studentId` in the URL
- **Per-message deflate** compression (`permessage-deflate`)
- **Structured logging** with configurable `LOG_LEVEL` (env: `LOG_LEVEL=debug|info|warn|error`)
- **Rate limiting** — max 2 process updates/sec per student (excess silently dropped)
- **Message validation** — rejects unknown `type` values or missing `data`
- **Metadata sanitisation** — device metadata capped at 4 KB per message
- **15-second heartbeat timeout** (was 10 s)

### Agent Connection

```
ws://host:8001/ws/agents/sessions/<sessionId>/students/<studentId>?token=<jwt>
```

`studentId` is the UUID from the `students` table.

On connect, the server:
1. Validates JWT has `role === "student"` and that `sessionId` + `studentId` match the token
2. Verifies the session is live (`is_live = true`)
3. Verifies the student UUID exists
4. Upserts a `session_students` row
5. Registers the agent socket in the in-memory `agentSockets` map
6. Starts a **15-second heartbeat timeout** timer
7. Sends an **ack** event with server configuration:
```json
{
  "type": "ack",
  "data": {
    "snapshotIntervalSec": 30,
    "deltaIntervalSec": 3,
    "heartbeatIntervalSec": 5
  }
}
```

### Teacher Connection

```
ws://host:8001/ws/teachers/sessions/<sessionId>/students/<rollNo>/processes
```

On connect, the server:
1. Verifies the teacher (from JWT) owns the session
2. Resolves `rollNo` → student UUID
3. Subscribes this teacher socket in `wsPublisher`
4. Sends the **current DB state** immediately: `process_snapshot`, `devices_snapshot`, `network_snapshot`
5. Replays up to 100 buffered events from Redis (if available)

On disconnect the teacher socket is automatically unsubscribed.

---

### Agent → Server Message Types

All messages: `{ "type": "<type>", "data": <payload> }`

| `type`                | `data` shape                                                               | Effect                                      |
|-----------------------|----------------------------------------------------------------------------|---------------------------------------------|
| `process_snapshot`    | `[{ pid, name, cpu, memory }]`                                             | Bulk upsert all processes                   |
| `process_new`         | `{ pid, name, cpu, memory }`                                               | Upsert a single new process                 |
| `process_update`      | `{ pid, cpu, memory, status }`                                             | Update cpu/memory/status for a process      |
| `process_end`         | `{ pid }`                                                                  | Mark process as `'ended'`                   |
| `devices_snapshot`    | `{ usb: [{id, name, metadata?}], external: [{id, name, metadata?}] }`     | Bulk upsert USB + external devices          |
| `device_connected`    | `{ id, name, type: 'usb'\|'external', metadata? }`                        | Upsert a single device                      |
| `device_disconnected` | `{ id }`                                                                   | Set `disconnected_at = now()` for device    |
| `network_snapshot`    | `{ ip, gateway, dns, activeConnections }`                                  | Upsert network info                         |
| `heartbeat`           | _any_                                                                      | Resets 10s offline timer + touches `last_seen_at` |

Every message is also **buffered in Redis** and **forwarded to all subscribed teacher sockets**.

---

### Server → Teacher Push Types

| `type`              | When sent                                                         |
|---------------------|-------------------------------------------------------------------|
| `process_snapshot`  | Immediately on teacher connect (current DB snapshot)              |
| `devices_snapshot`  | Immediately on teacher connect (current DB snapshot)              |
| `network_snapshot`  | Immediately on teacher connect (if data exists)                   |
| `agent_offline`     | When heartbeat times out (10s) or agent socket closes             |
| _all agent types_   | Forwarded in real-time as agent sends them                        |

`agent_offline` payload:
```json
{
  "type": "agent_offline",
  "data": { "studentId": "<uuid>", "lastSeen": "<ISO timestamp>" }
}
```

---

### Heartbeat & Liveness

Agents must send **any message** at least once every **15 seconds** to stay "online".  
Conventionally: `{ "type": "heartbeat" }`.

If no message arrives within 15 s:
- `agent_offline` is broadcast to all subscribed teachers
- The agent entry is removed from the in-memory map

---

### Redis Event Buffer

When Redis is available, every agent message is pushed to a list:

```
key:       events:<sessionId>:<studentId>
max items: 100  (LTRIM)
TTL:       1 hour
```

On teacher connect, buffered events are replayed in chronological order.  
If Redis is unavailable, no buffering occurs and teachers only see real-time events — the
server continues to operate normally.

---

## Services Layer

Services encapsulate all DB interaction logic and are shared between controllers and the WS server.

### `processService.js` — `live_processes` table

| Function                | Description                                      |
|-------------------------|--------------------------------------------------|
| `upsertProcess`         | INSERT … ON CONFLICT for a single process row    |
| `upsertProcessSnapshot` | Loop-based bulk upsert                           |
| `updateProcess`         | UPDATE cpu/memory/status for an existing process |
| `endProcess`            | Mark a PID as `'ended'`                          |
| `getProcesses`          | Fetch all processes for a student/session        |

### `deviceService.js` — `connected_devices` + `network_info` tables

| Function               | Description                                     |
|------------------------|-------------------------------------------------|
| `upsertDevice`         | INSERT … ON CONFLICT for a single device         |
| `upsertDevicesSnapshot`| Bulk upsert USB + external devices              |
| `disconnectDevice`     | Set `disconnected_at = now()`                   |
| `getDevices`           | Fetch currently-connected devices               |
| `upsertNetworkInfo`    | INSERT … ON CONFLICT for network state          |
| `getNetworkInfo`       | Fetch the latest network row                    |

### `sessionService.js` — session/student DB helpers

| Function               | Description                                       |
|------------------------|---------------------------------------------------|
| `getLiveSession`       | Fetch session row (used to verify `is_live`)       |
| `upsertSessionStudent` | Register/update a student in a session            |
| `touchLastSeen`        | Update `last_seen_at` on heartbeat                |
| `getStudentById`       | Fetch student row by UUID                         |
| `teacherOwnsSession`   | Ownership check used by the WS server auth        |

### `studentService.js` — student join-session helpers

| Function               | Description                                       |
|------------------------|---------------------------------------------------|
| `upsertStudent`        | INSERT … ON CONFLICT by roll_no, returns UUID     |
| `ensureSessionStudent` | INSERT … ON CONFLICT on session_students, touches last_seen |
| `getSessionById`       | SELECT session with password & is_live fields     |

### `wsPublisher.js` — in-memory pub/sub

Pure in-memory teacher socket registry, no external dependencies.

| Function           | Description                                                      |
|--------------------|------------------------------------------------------------------|
| `subscribe`        | Register a teacher WS to events for `(sessionId, studentId)`    |
| `unsubscribe`      | Remove that WS from a specific pair                              |
| `unsubscribeAll`   | Remove a WS from ALL subscriptions (on disconnect)               |
| `publish`          | Broadcast to all teachers watching a specific `(sessionId, studentId)` |
| `publishToSession` | Broadcast to all teachers watching any student in a session      |

---

## Middleware

### `auth.js`

**`authenticate(req, res, next)`** — Express middleware used on all protected routes.  
Reads `Authorization: Bearer <token>` (or `?token=` query param), verifies the JWT, and
attaches `req.user = { userId, email, role }`. Returns `401` on failure.

**`verifyToken(token)`** — Plain function (not Express middleware).  
Called directly by the WS server during the HTTP upgrade phase before the WebSocket handshake.

### `errorHandler.js`

Four-argument Express error handler, registered last in `app.js`.
- Logs the full stack to `console.error`
- Reads `err.status` / `err.statusCode` (defaults to `500`)
- Exposes the error message for 4xx; returns generic `"Server error"` for 5xx

---

## Utilities

`src/utils/helpers.js`

| Function       | Description                                                          |
|----------------|----------------------------------------------------------------------|
| `asyncHandler` | Wraps async route handlers — forwards rejected promises to `next`   |
| `httpError`    | Creates an `Error` with a `.status` property e.g. `httpError(404, 'Not found')` |
| `pick`         | Object key picker                                                    |
| `toCamel`      | Converts a single DB row `snake_case` → `camelCase`                  |
| `rowsToCamel`  | Maps an array of rows through `toCamel`                              |

`src/utils/cache.js`

| Function       | Description                                                          |
|----------------|----------------------------------------------------------------------|
| `cached(key, ttlMs, fetcher)` | Returns cached value if TTL not expired; else runs `fetcher()` and caches it |
| `invalidate(key)` | Remove a specific key from the cache                             |
| `clearCache()` | Flush all cached entries                                             |

Snapshot endpoints (`devices`, `network`, `processes`) use a **2-second TTL** cache so rapid
polling from the teacher dashboard doesn't hit the database on every request.

All REST API responses are converted to camelCase before sending.

---

## Scripts

### `npm run migrate`

Reads and executes every `.sql` file in `src/db/migrations/` in alphabetical order.
Uses `IF NOT EXISTS` DDL so it is **safe to re-run**.

### `npm run cleanup`

Deletes monitoring data older than **7 days** from:
- `live_processes` (by `updated_at`)
- `connected_devices` (by `connected_at`)
- `network_info` (by `updated_at`)
- `process_history` (by `recorded_at`)
- `sessions` where `is_live = false` (by `end_time`)

Designed to be scheduled as a cron job, e.g.:
```
0 3 * * * cd /path/to/backend && node src/scripts/cleanup.js
```

---

## Docker Compose

`docker-compose.yml` spins up:

| Service    | Image       | Host Port | Notes                                        |
|------------|-------------|-----------|----------------------------------------------|
| `postgres` | postgres:15 | **5433**  | Mapped to 5433 to avoid conflict with local Postgres |
| `redis`    | redis:7     | 6379      | Persistence: snapshot every 60s              |

> Update `DATABASE_URL` to use port 5433:
> `postgres://postgres:password@localhost:5433/lab_monitor`

Both services use named volumes (`pgdata`, `redisdata`) for persistence.

---

## Running Tests

```bash
npm test              # Jest unit tests (tests/unit/)
npm run test:e2e      # E2E flow test (tests/e2e/flow.test.js)
```

For manual WS agent simulation:
```bash
TOKEN=<jwt> SESSION_ID=<uuid> STUDENT_ID=<uuid> node tests/e2e/ws-agent-test.js
```

---

## Sample cURL Commands

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher@example.com","password":"secret"}'
```

### Create a Subject
```bash
curl -X POST http://localhost:8000/api/teacher/subjects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"name":"Data Structures","department":"CSE","year":2}'
```

### Create a Session
```bash
curl -X POST http://localhost:8000/api/teacher/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"subjectId":"<UUID>","batch":"A","lab":"Lab-101","date":"2026-03-04","startTime":"09:00"}'
```

### Dashboard
```bash
curl http://localhost:8000/api/teacher/dashboard \
  -H "Authorization: Bearer <TOKEN>"
```

### End a Session
```bash
curl -X POST http://localhost:8000/api/teacher/sessions/<SESSION_ID>/end \
  -H "Authorization: Bearer <TOKEN>"
```

---

## Design Notes & Decisions

### Two-process architecture
The HTTP and WS servers are separate processes that share the same Postgres database.  
This means they can be scaled and deployed independently. A WS crash does not affect the REST API.
The WS server is stateful (in-memory agent map + publisher registry); the HTTP server is stateless.

### Authentication
JWT is stateless. The same token works for both HTTP and WebSocket connections.  
Expiry defaults to 8 hours, configurable via `JWT_EXPIRES_IN`.

> **Security Note:** `authController.js` currently performs a plain-text string comparison
> (`password === teacher.password_hash`). `bcrypt` is already a listed dependency — use
> `bcrypt.compare(password, teacher.password_hash)` before deploying to production.

### Snake_case → camelCase
All PostgreSQL columns use `snake_case`. The `toCamel` / `rowsToCamel` helpers in `helpers.js`
convert every REST response to `camelCase` automatically, matching frontend JavaScript conventions.

### Upsert pattern
All "live" monitoring tables (`live_processes`, `connected_devices`, `network_info`,
`session_students`) use `INSERT … ON CONFLICT … DO UPDATE`. This makes agent messages
**idempotent** — a reconnecting agent can resend a full snapshot without creating duplicate rows.

### Redis as optional enhancement
The WS server attempts to connect to Redis at startup and gracefully degrades if it is
unavailable. All core features (real-time streaming, DB persistence) work without Redis.
Redis only enhances the experience for teachers who join a session mid-way.

### No ORM
Raw, parameterised SQL is used throughout (`$1, $2, ...` placeholders via `node-postgres`).
This gives full visibility and control over every query, with zero ORM overhead.

### DB connection pool
`pg.Pool` is configured with `max: 20` connections, a 30s idle timeout, and a 5s connection
timeout. Queries taking longer than **500ms** are logged as warnings to aid performance debugging.

### Graceful shutdown
Both servers (`server.js` and `ws-server.js`) listen for `SIGINT` / `SIGTERM` and cleanly close
the HTTP/WS server, Redis connection, and Postgres pool before exiting.

---

## License

MIT

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Postgres and Redis connection strings
```

### 3. Create database and run migrations

```bash
# Create the database (if it doesn't exist)
createdb lab_monitor

# Run migrations
npm run migrate
```

### 4. Seed test data (optional — needed for E2E tests)

```bash
node tests/e2e/seed.js
```

### 5. Start servers

```bash
# Terminal 1 — HTTP API server (port 8000)
npm start

# Terminal 2 — WebSocket server (port 8001)
npm run ws
```

For development with auto-reload:

```bash
npm run dev      # HTTP server
npm run dev:ws   # WS server
```

---

## Running Tests

### Unit tests (Jest)

```bash
npm test
```

### E2E flow test

Requires running servers and seeded data:

```bash
node tests/e2e/flow.test.js
```

### WebSocket agent simulation

```bash
TOKEN=<jwt> SESSION_ID=<uuid> STUDENT_ID=<uuid> node tests/e2e/ws-agent-test.js
```

---

## Scheduled Cleanup

Delete monitoring data older than 7 days:

```bash
npm run cleanup
```

Add to cron for daily cleanup:

```
0 3 * * * cd /path/to/backend && node src/scripts/cleanup.js
```

---

## API Endpoints

Base URL: `http://localhost:8000/api`

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | No | Login with email/password, returns JWT |
| POST | `/api/auth/logout` | No | Clear session cookie (optional) |

### Student Agent

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/students/join-session` | No | Agent joins live session, returns student JWT |

### Subjects

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/api/teacher/subjects` | Yes | List teacher's subjects with stats |
| POST | `/api/teacher/subjects` | Yes | Create a new subject |

### Sessions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/teacher/sessions` | Yes | Create a new live session |
| GET  | `/api/teacher/sessions?status=all\|live\|ended` | Yes | List sessions |
| GET  | `/api/teacher/sessions/:sessionId` | Yes | Get session detail |
| POST | `/api/teacher/sessions/:sessionId/end` | Yes | End a session |

### Students

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/teacher/sessions/:sessionId/students` | Yes | List students in session |
| GET | `/api/teacher/students/:rollNo` | Yes | Student profile + enrolled subjects |
| GET | `/api/teacher/students/:rollNo/devices?sessionId=...` | Yes | Connected devices |
| GET | `/api/teacher/students/:rollNo/network?sessionId=...` | Yes | Latest network info |

### Processes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/teacher/sessions/:sessionId/students/:rollNo/processes` | Yes | Live process snapshot |

### Dashboard

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/teacher/dashboard` | Yes | Aggregated teacher stats |

---

## WebSocket Endpoints

Base URL: `ws://localhost:8001`

### Agent (student-side telemetry)

**Path:** `/ws/agents/sessions/:sessionId/students/:studentId`

Auth: JWT via `Authorization: Bearer <token>` header or `?token=<jwt>` query param.

**Inbound message types:**
- `process_snapshot` — Full process list
- `process_new` — New process started
- `process_update` — Process stats updated
- `process_end` — Process ended
- `devices_snapshot` — Full device list
- `device_connected` — Device plugged in
- `device_disconnected` — Device removed
- `network_snapshot` — Network info update
- `heartbeat` — Keep-alive ping

### Teacher (viewer)

**Path:** `/ws/teachers/sessions/:sessionId/students/:rollNo/processes`

On connect: receives `process_snapshot`, `devices_snapshot`, `network_snapshot`.
Then receives forwarded real-time events from agent.

---

## Sample cURL Commands

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e@test.com","password":"password123"}'
```

### Student Join Session (Agent)

```bash
curl -X POST http://localhost:8000/api/students/join-session \
  -H "Content-Type: application/json" \
  -d '{"rollNo":"CS2021001","sessionId":"<SESSION_ID>","password":"optional"}'
```

### Create Subject

```bash
curl -X POST http://localhost:8000/api/teacher/subjects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"name":"Data Structures","department":"CS","year":2}'
```

### Create Session

```bash
curl -X POST http://localhost:8000/api/teacher/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"subjectId":"<SUBJECT_ID>","batch":"A","lab":"Lab-101","date":"2026-03-03","startTime":"09:00"}'
```

### Get Students in Session

```bash
curl http://localhost:8000/api/teacher/sessions/<SESSION_ID>/students \
  -H "Authorization: Bearer <TOKEN>"
```

### Get Live Processes

```bash
curl http://localhost:8000/api/teacher/sessions/<SESSION_ID>/students/STU001/processes \
  -H "Authorization: Bearer <TOKEN>"
```

### End Session

```bash
curl -X POST http://localhost:8000/api/teacher/sessions/<SESSION_ID>/end \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>"
```

### Dashboard

```bash
curl http://localhost:8000/api/teacher/dashboard \
  -H "Authorization: Bearer <TOKEN>"
```

---

## Project Structure

```
backend/
├── package.json
├── .env.example
├── README.md
├── src/
│   ├── app.js                   # Express app setup
│   ├── server.js                # HTTP server entry
│   ├── ws-server.js             # WebSocket server entry
│   ├── config/
│   │   └── index.js             # Env config + Redis client
│   ├── db/
│   │   ├── index.js             # Postgres pool + query helper
│   │   └── migrations/
│   │       └── 001_create_tables.sql
│   ├── routes/
│   │   ├── auth.js
│   │   ├── subjects.js
│   │   ├── sessions.js
│   │   ├── students.js          # Includes public /join-session route
│   │   └── dashboard.js
│   ├── controllers/
│   │   ├── authController.js
│   │   ├── subjectsController.js
│   │   ├── sessionsController.js
│   │   ├── studentsController.js # joinSession + 2s cache on snapshot endpoints
│   │   └── dashboardController.js
│   ├── services/
│   │   ├── sessionService.js
│   │   ├── studentService.js    # upsertStudent, ensureSessionStudent, getSessionById
│   │   ├── deviceService.js
│   │   ├── processService.js
│   │   └── wsPublisher.js
│   ├── middleware/
│   │   ├── auth.js
│   │   └── errorHandler.js
│   ├── scripts/
│   │   ├── migrate.js
│   │   └── cleanup.js
│   └── utils/
│       ├── helpers.js
│       └── cache.js             # In-memory TTL cache utility
└── tests/
    ├── unit/
    │   ├── auth.test.js
    │   └── dashboard.test.js
    └── e2e/
        ├── flow.test.js
        ├── seed.js
        └── ws-agent-test.js
```

---

## License

MIT
