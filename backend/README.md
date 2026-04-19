# Lab Guardian Backend — Offline-First Exam Monitoring

A Node.js + PostgreSQL backend for the **Lab Guardian offline-first exam monitoring system**. 
Receives synced data from student agents and provides a dashboard API for teachers to monitor exams.

---

## Architecture

```
Student Agents (Python/SQLite)
         ↓
   HTTP POST /api/logs/receive
   (Batch upload when internet available)
         ↓
┌─────────────────────────────────────────┐
│ Backend Server (Node.js + Express)      │
│ - Receives log batches                  │
│ - Stores in PostgreSQL                  │
│ - No authentication required            │
│ - Serves dashboard data                 │
└──────────────┬──────────────────────────┘
               ↓
         PostgreSQL Database
               ↓
┌─────────────────────────────────────────┐
│ Teacher Dashboard (React)               │
│ - Polls /api/dashboard/students         │
│ - Views student activity                │
│ - Ends all sessions with secret key     │
└─────────────────────────────────────────┘
```

---

## Tech Stack

| Layer          | Technology                        |
|----------------|-----------------------------------|
| Runtime        | Node.js (ES Modules)              |
| HTTP Server    | Express 4                         |
| Database       | PostgreSQL 15 via `pg`            |
| Config         | `dotenv`                          |

---

## Getting Started

### Prerequisites

| Dependency | Version |
|------------|---------|
| Node.js    | ≥ 18    |
| PostgreSQL | ≥ 14    |

### 1. Install dependencies

```bash
cd backend
npm install
```

### 2. Configure environment

Create `.env` file:

```env
PORT=8000
DATABASE_URL=postgres://postgres:password@localhost:5432/lab_guardian
```

### 3. Create database and run migrations

```bash
# Create the database
createdb lab_guardian

# Run migrations
npm run migrate
```

### 4. Start server

```bash
# Development (with auto-reload)
npm run dev

# Production
npm start
```

Server runs on `http://localhost:8000`

---

## API Reference

### Health Check

**GET /api/health**

Response:
```json
{ "status": "ok" }
```

---

### Sync Endpoints (Agent → Backend)

**POST /api/logs/receive**

Receive batch of logs from student agent. No authentication required.

Request:
```json
{
  "session_id": "uuid",
  "timestamp": "2024-01-01T10:00:00Z",
  "processes": [
    {
      "pid": 1234,
      "process_name": "chrome",
      "cpu_percent": 12.5,
      "memory_mb": 350.0,
      "status": "running",
      "risk_level": "medium",
      "category": "browser",
      "is_incognito": false
    }
  ],
  "devices": [
    {
      "device_id": "USB001",
      "device_name": "SanDisk USB",
      "device_type": "usb",
      "readable_name": "SanDisk Cruzer",
      "risk_level": "high",
      "connected_at": 1704067200.0
    }
  ],
  "terminal_events": [
    {
      "tool": "curl",
      "remote_ip": "140.82.121.4",
      "remote_host": "github.com",
      "remote_port": 443,
      "pid": 5678,
      "event_type": "terminal_request",
      "risk_level": "high"
    }
  ],
  "browser_history": [
    {
      "url": "https://chatgpt.com",
      "title": "ChatGPT",
      "visit_count": 1,
      "last_visited": 1704067200.0,
      "browser": "Chrome"
    }
  ]
}
```

Response:
```json
{
  "message": "Logs received successfully",
  "totalRecords": 15,
  "session_id": "uuid"
}
```

---

### Dashboard Endpoints (Backend → Teacher)

**GET /api/dashboard/students?lab_no=L01&time_from=...&time_to=...**

Get all active students grouped by start time. No authentication required.

Query Parameters:
- `lab_no` (optional) — Filter by lab number (e.g., "L01")
- `time_from` (optional) — Filter by start time (ISO timestamp)
- `time_to` (optional) — Filter by end time (ISO timestamp)

Response:
```json
{
  "total": 25,
  "grouped": [
    {
      "start_time": "2024-01-01T10:00:00Z",
      "students": [
        {
          "session_id": "uuid",
          "roll_no": "CS2021001",
          "lab_no": "L01",
          "start_time": 1704067200.0,
          "process_count": 15,
          "device_count": 0,
          "terminal_event_count": 2,
          "browser_history_count": 5
        }
      ]
    }
  ]
}
```

---

**GET /api/dashboard/student/:sessionId**

Get detailed activity for a specific student. No authentication required.

Response:
```json
{
  "session": {
    "id": "uuid",
    "roll_no": "CS2021001",
    "lab_no": "L01",
    "start_time": 1704067200.0,
    "end_time": null
  },
  "processes": [...],
  "devices": [...],
  "terminal_events": [...],
  "browser_history": [...]
}
```

---

### Exam Management

**POST /api/exam/end-all**

End all active exam sessions with secret key verification. No authentication required.

Request:
```json
{
  "secret_key": "80085"
}
```

Response:
```json
{
  "message": "All sessions ended",
  "ended_count": 25,
  "sessions": [
    { "id": "uuid", "roll_no": "CS2021001", "lab_no": "L01" }
  ]
}
```

---

## Database Schema

### exam_sessions
Tracks exam instances.

| Column              | Type    | Description                    |
|---------------------|---------|--------------------------------|
| `id`                | UUID    | Primary key                    |
| `roll_no`           | TEXT    | Student roll number            |
| `lab_no`            | TEXT    | Lab number (L01-L12)           |
| `start_time`        | DOUBLE  | Unix timestamp                 |
| `end_time`          | DOUBLE  | Unix timestamp (NULL=active)   |
| `secret_key_verified` | INT   | 1 if ended with secret key     |
| `synced`            | INT     | Sync status                    |

### live_processes
Process monitoring data from agents.

| Column         | Type         | Description              |
|----------------|--------------|--------------------------|
| `id`           | UUID         | Primary key              |
| `session_id`   | UUID         | FK → exam_sessions       |
| `student_id`   | UUID         | Student identifier       |
| `pid`          | INT          | Process ID               |
| `process_name` | TEXT         | Process name             |
| `cpu_percent`  | NUMERIC(5,2) | CPU usage                |
| `memory_mb`    | NUMERIC(10,2)| Memory usage             |
| `status`       | TEXT         | running/ended            |
| `risk_level`   | TEXT         | normal/medium/high       |
| `category`     | TEXT         | Process category         |
| `is_incognito` | BOOLEAN      | Incognito mode detected  |

### connected_devices
USB/external device tracking.

| Column          | Type    | Description              |
|-----------------|---------|--------------------------|
| `id`            | UUID    | Primary key              |
| `session_id`    | UUID    | FK → exam_sessions       |
| `student_id`    | UUID    | Student identifier       |
| `device_id`     | TEXT    | Device identifier        |
| `device_name`   | TEXT    | Device name              |
| `device_type`   | TEXT    | usb/external             |
| `readable_name` | TEXT    | Human-readable name      |
| `risk_level`    | TEXT    | normal/high              |
| `connected_at`  | TIMESTZ | Connection time          |
| `disconnected_at`| TIMESTZ| Disconnection time       |

### terminal_events
Terminal command and network connection events.

| Column          | Type    | Description              |
|-----------------|---------|--------------------------|
| `id`            | UUID    | Primary key              |
| `session_id`    | UUID    | FK → exam_sessions       |
| `student_id`    | UUID    | Student identifier       |
| `tool`          | TEXT    | Tool name (curl, git...) |
| `remote_ip`     | TEXT    | Remote IP address        |
| `remote_host`   | TEXT    | Resolved hostname        |
| `remote_port`   | INT     | Remote port              |
| `pid`           | INT     | Process ID               |
| `event_type`    | TEXT    | terminal_request/command |
| `full_command`  | TEXT    | Full command (auditd)    |
| `risk_level`    | TEXT    | normal/medium/high       |
| `detected_at`   | TIMESTZ | Detection time           |

### browser_history
Browser URL history.

| Column         | Type    | Description              |
|----------------|---------|--------------------------|
| `id`           | UUID    | Primary key              |
| `session_id`   | UUID    | FK → exam_sessions       |
| `student_id`   | UUID    | Student identifier       |
| `url`          | TEXT    | Visited URL              |
| `title`        | TEXT    | Page title               |
| `visit_count`  | INT     | Number of visits         |
| `last_visited` | TIMESTZ | Last visit time          |
| `browser`      | TEXT    | Browser name             |

---

## Project Structure

```
backend/
├── package.json
├── .env                      # Environment variables
├── src/
│   ├── app.js                # Express app setup
│   ├── server.js             # HTTP server entry
│   │
│   ├── config/
│   │   └── index.js          # Environment config
│   │
│   ├── db/
│   │   ├── index.js          # PostgreSQL pool
│   │   └── migrations/
│   │       ├── 001_create_tables.sql
│   │       ├── 002_add_insights_columns.sql
│   │       ├── 003_add_terminal_events.sql
│   │       └── 004_add_offline_exam_tables.sql
│   │
│   ├── routes/
│   │   └── sync.js           # Sync and dashboard routes
│   │
│   ├── controllers/
│   │   └── syncController.js # Log receiving + dashboard
│   │
│   ├── middleware/
│   │   └── errorHandler.js   # Error handling
│   │
│   ├── services/
│   │   ├── processService.js # Process DB operations
│   │   └── deviceService.js  # Device/network DB ops
│   │
│   ├── utils/
│   │   └── helpers.js        # Utility functions
│   │
│   └── scripts/
│       ├── migrate.js        # Run migrations
│       └── cleanup.js        # Clean old data
```

---

## Data Flow

### Student Agent Sync

```
1. Agent checks internet (every 10s)
2. If connected, collects unsynced records from SQLite
3. POST /api/logs/receive with batch data
4. Backend stores in PostgreSQL
5. Agent marks records as synced
6. Repeat every 30 seconds
```

### Teacher Dashboard

```
1. Dashboard polls /api/dashboard/students (every 5-10s)
2. Backend returns students grouped by start time
3. Teacher clicks student → /api/dashboard/student/:sessionId
4. Backend returns detailed activity
```

### Session Termination

```
1. Teacher clicks "End All Sessions"
2. POST /api/exam/end-all with secret_key
3. Backend verifies key (80085)
4. Updates all active sessions with end_time
5. Agents detect session end and close
```

---

## Scheduled Cleanup

Delete monitoring data older than 7 days:

```bash
npm run cleanup
```

Add to cron for daily cleanup at 3 AM:

```
0 3 * * * cd /path/to/backend && node src/scripts/cleanup.js
```

---

## Environment Variables

| Variable       | Default                                      | Description              |
|----------------|----------------------------------------------|--------------------------|
| `PORT`         | `8000`                                       | Server port              |
| `DATABASE_URL` | `postgres://postgres:password@localhost:5432/lab_guardian` | Database connection |
| `CORS_ORIGINS` | `*`                                          | Allowed CORS origins     |

---

## Design Decisions

### No Authentication
- Designed for isolated exam environment
- Teachers access dashboard directly (no login)
- Secret key (80085) protects session termination
- Network-level security recommended (firewall, VPN)

### Offline-First Architecture
- Agents work 100% offline with local SQLite
- HTTP sync instead of WebSocket (no persistent connection needed)
- Batch uploads reduce server load
- Automatic retry on failure

### Append-Only Logging
- Monitoring data is never deleted during active exam
- Ensures complete audit trail
- Cleanup happens post-exam via scheduled script

### Simple REST API
- No WebSocket complexity
- Easy to debug and test
- Works with any HTTP client
- Stateless and scalable

---

## Troubleshooting

### Database connection failed
```bash
# Check PostgreSQL is running
pg_isready

# Check DATABASE_URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Migration errors
```bash
# Drop and recreate database (WARNING: deletes all data)
dropdb lab_guardian
createdb lab_guardian
npm run migrate
```

### Server won't start
```bash
# Check port availability
lsof -i :8000

# Check Node.js version
node --version  # Should be ≥ 18

# Install dependencies
npm install
```

---

## License

MIT
