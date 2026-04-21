# LabGuardian Backend

This README documents only the current backend implementation in this repository.

Primary backend root: [backend](backend)

## 1. Backend Role

Current backend behavior:

- Receives telemetry export batches from the LabGuardian client application.
- Stores ingested telemetry in PostgreSQL tables.
- Exposes a health endpoint.

Current backend APIs mounted in code:

- GET /api/health
- POST /api/telemetry/ingest

Route mounting source: [backend/src/app.js](backend/src/app.js)

## 2. Backend Folder Structure

Important backend files and folders:

- [backend/src/app.js](backend/src/app.js)
  - Express app setup
  - CORS and JSON body middleware
  - Route mounting and fallback handlers

- [backend/src/server.js](backend/src/server.js)
  - HTTP server startup
  - Graceful shutdown and PostgreSQL pool close

- [backend/src/routes/telemetry.js](backend/src/routes/telemetry.js)
  - Telemetry route declaration

- [backend/src/controllers/telemetryController.js](backend/src/controllers/telemetryController.js)
  - Telemetry ingest request handling and DB writes

- [backend/src/db/index.js](backend/src/db/index.js)
  - PostgreSQL pool
  - Shared query helper

- [backend/src/config/index.js](backend/src/config/index.js)
  - Runtime config for PORT and DATABASE_URL

- [backend/src/middleware/errorHandler.js](backend/src/middleware/errorHandler.js)
  - Express error response formatting

- [backend/src/db/migrations](backend/src/db/migrations)
  - SQL schema files

- [backend/src/scripts/migrate.js](backend/src/scripts/migrate.js)
  - Migration runner

- [backend/src/scripts/cleanup.js](backend/src/scripts/cleanup.js)
  - Data cleanup script

- [backend/src/services/deviceService.js](backend/src/services/deviceService.js)
- [backend/src/services/networkService.js](backend/src/services/networkService.js)
- [backend/src/services/processService.js](backend/src/services/processService.js)
  - Database service functions available in source

## 3. Runtime and Configuration

Source: [backend/src/config/index.js](backend/src/config/index.js)

Config fields currently used by backend app startup:

- port
  - from environment variable PORT
  - default 8000

- databaseUrl
  - from environment variable DATABASE_URL
  - default postgres://postgres:password@localhost:5432/lab_monitor

## 4. HTTP API Overview

Mounted in [backend/src/app.js](backend/src/app.js):

- GET /api/health
- /api/telemetry route group

Telemetry route group source: [backend/src/routes/telemetry.js](backend/src/routes/telemetry.js)

Contains:

- POST /ingest

So full telemetry endpoint URL is:

- POST /api/telemetry/ingest

## 5. API Documentation

## 5.1 GET /api/health

Endpoint info:

- URL: /api/health
- Method: GET
- Purpose: health check response
- Handler location: [backend/src/app.js](backend/src/app.js)

Request data:

- No request body

Response format:

- Status 200

  {
    "status": "ok"
  }

Internal handling:

- Express route directly returns static JSON object.

## 5.2 POST /api/telemetry/ingest

Endpoint info:

- URL: /api/telemetry/ingest
- Method: POST
- Purpose: ingest telemetry batch and persist to PostgreSQL
- Route file: [backend/src/routes/telemetry.js](backend/src/routes/telemetry.js)
- Controller function: ingestTelemetry in [backend/src/controllers/telemetryController.js](backend/src/controllers/telemetryController.js)

### Request Data

Exact top-level request body shape used by controller:

{
  "sessionId": "string",
  "rollNo": "string",
  "labNo": "string",
  "name": "string",
  "devices": [],
  "browserHistory": [],
  "processes": [],
  "terminalEvents": []
}

Controller defaults:

- devices defaults to [] if omitted
- browserHistory defaults to [] if omitted
- processes defaults to [] if omitted
- terminalEvents defaults to [] if omitted

Validation rule in controller:

- sessionId and rollNo are required

If either is missing:

- Status 400

  {
    "error": "Missing required fields"
  }

### Request Field Definitions and Sources

Top-level fields:

- sessionId
  - type: string
  - source: client application export payload

- rollNo
  - type: string
  - source: client application export payload

- labNo
  - type: string
  - source: client application export payload

- name
  - type: string
  - source: client application export payload

- devices
  - type: array of device objects
  - source: client application export payload

- browserHistory
  - type: array of browser history objects
  - source: client application export payload

- processes
  - type: array of process objects
  - source: client application export payload

- terminalEvents
  - type: array of terminal event objects
  - source: client application export payload

Frontend to backend API calls present in code:

- frontend currently calls GET telemetry endpoints through [frontend/src/services/api.js](frontend/src/services/api.js)
- there is no frontend POST call to /api/telemetry/ingest in current frontend source

### Client-Sent Monitoring Data Formats

The backend controller reads the following object fields from each array item.

Device object fields read by backend:

{
  "id": "string|null",
  "name": "string|null",
  "readable_name": "string|null",
  "device_type": "string|null",
  "metadata": "object|string|null",
  "risk_level": "string|null",
  "message": "string|null"
}

Browser history object fields read by backend:

{
  "url": "string|null",
  "title": "string|null",
  "visit_count": "number|null",
  "last_visited": "number|null",
  "browser": "string|null"
}

Process object fields read by backend:

{
  "pid": "number|null",
  "name": "string|null",
  "label": "string|null",
  "cpu": "number|null",
  "memory": "number|null",
  "status": "string|null",
  "risk_level": "string|null",
  "category": "string|null"
}

Terminal event object fields read by backend:

{
  "event_type": "string|null",
  "tool": "string|null",
  "remote_ip": "string|null",
  "remote_host": "string|null",
  "remote_port": "number|null",
  "pid": "number|null",
  "full_command": "string|null",
  "risk_level": "string|null",
  "message": "string|null",
  "detected_at": "string|null"
}

### Full Example Request JSON

{
  "sessionId": "S-ABC-001",
  "rollNo": "CS22001",
  "labNo": "L01",
  "name": "Student One",
  "devices": [
    {
      "id": "usb-1",
      "name": "USB Drive",
      "readable_name": "SanDisk Ultra",
      "device_type": "usb",
      "metadata": {
        "vendor": "SanDisk",
        "model": "Ultra"
      },
      "risk_level": "medium",
      "message": "USB connected"
    }
  ],
  "browserHistory": [
    {
      "url": "https://example.com",
      "title": "Example",
      "visit_count": 2,
      "last_visited": 1710000000,
      "browser": "Chrome"
    }
  ],
  "processes": [
    {
      "pid": 1234,
      "name": "python3",
      "label": "Python 3 Interpreter",
      "cpu": 12.5,
      "memory": 220.4,
      "status": "running",
      "risk_level": "medium",
      "category": "suspicious"
    }
  ],
  "terminalEvents": [
    {
      "event_type": "terminal_command",
      "tool": "ssh",
      "remote_ip": "192.168.1.10",
      "remote_host": "host.local",
      "remote_port": 22,
      "pid": 1234,
      "full_command": "ssh user@host.local",
      "risk_level": "high",
      "message": "Terminal command",
      "detected_at": "2026-04-21T10:00:00Z"
    }
  ]
}

### Response Format

Success response:

- Status 200

  {
    "success": true
  }

Validation failure response:

- Status 400

  {
    "error": "Missing required fields"
  }

Ingest failure response:

- Status 500

  {
    "error": "Ingest failed"
  }

### Internal Handling Flow

Handler location:

- Function ingestTelemetry in [backend/src/controllers/telemetryController.js](backend/src/controllers/telemetryController.js)

Processing sequence in code:

1. Read request body fields.
2. Validate required sessionId and rollNo.
3. Normalize session id using UUID validation or UUID v5 generation.
4. Ensure teacher row exists or is updated.
5. Insert subject row and get subject id.
6. Ensure session row exists by id.
7. Ensure student row exists by roll number.
8. Ensure session_students relation exists.
9. Insert each device row into connected_devices.
10. Insert each browserHistory row into browser_history.
11. Insert each process row into live_processes.
12. Insert each terminalEvents row into terminal_events.
13. Return success JSON.

## 6. Database Storage

## 6.1 Database Access Layer

Source: [backend/src/db/index.js](backend/src/db/index.js)

Current DB layer behavior:

- Creates pg Pool with connectionString from config.databaseUrl
- Exposes query function for parameterized SQL execution
- Exposes getClient for transactional use

## 6.2 Migration Files

Schema source files:

- [backend/src/db/migrations/001_create_tables.sql](backend/src/db/migrations/001_create_tables.sql)
- [backend/src/db/migrations/002_add_insights_columns.sql](backend/src/db/migrations/002_add_insights_columns.sql)
- [backend/src/db/migrations/003_add_terminal_events.sql](backend/src/db/migrations/003_add_terminal_events.sql)
- [backend/src/db/migrations/004_add_browser_history.sql](backend/src/db/migrations/004_add_browser_history.sql)

## 6.3 Tables Used by Ingest Endpoint

Identity and linkage tables written by ingest flow:

- teachers
- subjects
- sessions
- students
- session_students

Telemetry tables written by ingest flow:

- connected_devices
- browser_history
- live_processes
- terminal_events

## 6.4 Request to Database Field Mapping

Device mapping in ingest:

Request object path -> DB column

- devices[].id -> connected_devices.device_id
- devices[].name or devices[].readable_name or default string -> connected_devices.device_name
- devices[].device_type or default usb -> connected_devices.device_type
- devices[].metadata (object or string) -> connected_devices.metadata
- devices[].readable_name -> connected_devices.readable_name
- devices[].risk_level -> connected_devices.risk_level
- devices[].message -> connected_devices.message

Browser history mapping in ingest:

- browserHistory[].url -> browser_history.url
- browserHistory[].title -> browser_history.title
- browserHistory[].visit_count -> browser_history.visit_count
- browserHistory[].last_visited -> browser_history.last_visited
- browserHistory[].browser -> browser_history.browser
- resolvedSessionId -> browser_history.session_id
- rollNo -> browser_history.roll_no

Process mapping in ingest:

- processes[].pid -> live_processes.pid
- processes[].name or processes[].label -> live_processes.process_name
- processes[].cpu -> live_processes.cpu_percent
- processes[].memory -> live_processes.memory_mb
- processes[].status or default running -> live_processes.status
- processes[].risk_level -> live_processes.risk_level
- processes[].category -> live_processes.category

Terminal event mapping in ingest:

- terminalEvents[].event_type -> terminal_events.event_type
- terminalEvents[].tool -> terminal_events.tool
- terminalEvents[].remote_ip -> terminal_events.remote_ip
- terminalEvents[].remote_host -> terminal_events.remote_host
- terminalEvents[].remote_port -> terminal_events.remote_port
- terminalEvents[].pid -> terminal_events.pid
- terminalEvents[].full_command -> terminal_events.full_command
- terminalEvents[].risk_level -> terminal_events.risk_level
- terminalEvents[].message -> terminal_events.message
- terminalEvents[].detected_at -> terminal_events.detected_at via COALESCE with now()

## 7. Data Flow

## 7.1 Client to Backend

Current ingest path:

- Client application sends telemetry export payload to POST /api/telemetry/ingest.
- Backend controller parses payload arrays and inserts data into PostgreSQL.

Client request origin in repository:

- Export request constructed and sent from [Lab_guardian/lab_guardian/gui.py](Lab_guardian/lab_guardian/gui.py)

## 7.2 Backend to Database

Current write path:

- Controller calls shared query function from [backend/src/db/index.js](backend/src/db/index.js).
- Insert statements execute for identity and telemetry records.

## 7.3 Backend to Frontend

Current response serving behavior:

- Backend serves:
  - GET /api/health response
  - POST /api/telemetry/ingest response

Frontend calls present in source:

- Frontend requests GET telemetry read endpoints from [frontend/src/services/api.js](frontend/src/services/api.js)

## 8. Services Layer in Current Backend Source

Service files present:

- [backend/src/services/deviceService.js](backend/src/services/deviceService.js)
- [backend/src/services/networkService.js](backend/src/services/networkService.js)
- [backend/src/services/processService.js](backend/src/services/processService.js)

These files define DB helper functions for:

- connected_devices upsert and retrieval
- network_info upsert and retrieval
- domain_activity upsert and retrieval
- terminal_events insert and retrieval
- live_processes upsert/update/end and retrieval

## 9. Supporting Backend Scripts

Migration script:

- File: [backend/src/scripts/migrate.js](backend/src/scripts/migrate.js)
- Command: npm run migrate
- Behavior: reads SQL files in migrations directory, sorted by filename, executes sequentially

Cleanup script:

- File: [backend/src/scripts/cleanup.js](backend/src/scripts/cleanup.js)
- Command: npm run cleanup
- Behavior: deletes rows older than retention window from selected tables and ended sessions

## 10. Setup and Run

Backend package file: [backend/package.json](backend/package.json)

Install:

1. cd backend
2. npm install

Run API server (dev):

1. cd backend
2. npm run dev

Run API server (start):

1. cd backend
2. npm start

Run migrations:

1. cd backend
2. set DATABASE_URL environment variable
3. npm run migrate

Docker compose file:

- [backend/docker-compose.yml](backend/docker-compose.yml)

Compose services defined:

- postgres service
- backend service

## 11. Complete Backend API Table

| Method | URL | Purpose | Handler File |
|---|---|---|---|
| GET | /api/health | Health check | [backend/src/app.js](backend/src/app.js) |
| POST | /api/telemetry/ingest | Telemetry batch ingestion | [backend/src/controllers/telemetryController.js](backend/src/controllers/telemetryController.js) |

## 12. Error Response Handling

Error handler source: [backend/src/middleware/errorHandler.js](backend/src/middleware/errorHandler.js)

Current behavior:

- Uses err.status or err.statusCode when present, otherwise 500
- Returns JSON response with error field

Response shape:

{
  "error": "message string"
}
