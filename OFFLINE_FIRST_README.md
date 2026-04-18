# LabGuardian - Offline-First Exam Monitoring System

A comprehensive exam monitoring solution that works **offline-first** with automatic sync when internet is available. Perfect for computer labs with unreliable internet connectivity.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ STUDENT MACHINE (Ubuntu)                                     │
│                                                               │
│  ┌──────────────────────────────────────────────┐           │
│  │ Agent UI (PyQt5)                              │           │
│  │ - Roll No + Lab No input                     │           │
│  │ - Real-time activity display                 │           │
│  │ - Status indicators                          │           │
│  └──────────────────────────────────────────────┘           │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────┐           │
│  │ Local SQLite Database (~/.lab_guardian/)     │           │
│  │ - All monitoring data stored locally         │           │
│  │ - Works 100% offline                         │           │
│  └──────────────────────────────────────────────┘           │
│                          ↓ (when internet available)         │
│  ┌──────────────────────────────────────────────┐           │
│  │ Sync Manager                                  │           │
│  │ - Uploads only unsynced logs                 │           │
│  │ - Retries automatically                      │           │
│  └──────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
                          ↓ HTTP POST /api/logs/receive
┌─────────────────────────────────────────────────────────────┐
│ BACKEND SERVER (Node.js + PostgreSQL)                       │
│ - No authentication required                                │
│ - Receives log batches from students                        │
│ - Stores in PostgreSQL                                      │
│ - Serves dashboard data                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ TEACHER DASHBOARD (React)                                   │
│ - Direct access (no login)                                  │
│ - Students sorted by start time (descending)                │
│ - Filters: Lab No, Time Range                               │
│ - Click student → Full activity view                        │
│ - "End All Sessions" with secret key (80085)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### For Students (Agent Installation)

1. **Install the agent** (one-time):
```bash
sudo dpkg -i lab-guardian-agent-2.0.0.deb
sudo apt-get install -f  # Install dependencies if needed
```

2. **Start the agent**:
```bash
lab-guardian start
```
Or launch from Applications menu → "Lab Guardian Agent"

3. **Enter your details**:
   - Roll Number (e.g., CS2021001)
   - Lab Number (L01 to L12)
   - Click "Start Exam Session"

4. **During the exam**:
   - The agent monitors all activities locally
   - Data is saved to `~/.lab_guardian/exam_data.db`
   - If internet is available, data syncs automatically
   - You **cannot** end the session yourself

5. **End of exam**:
   - Teacher will provide the secret key
   - Click "End Session" and enter the key
   - Session ends and data is saved

### For Teachers (Dashboard)

1. **Start the backend**:
```bash
cd backend
npm install
npm run migrate  # Run database migrations
npm run dev      # Start server on port 8000
```

2. **Start the frontend**:
```bash
cd frontend
npm install
npm run dev      # Start on http://localhost:5173
```

3. **Access the dashboard**:
   - Open http://localhost:5173
   - No login required!
   - Students appear automatically as they start exams

4. **Monitor students**:
   - View students grouped by start time
   - Filter by lab number or time range
   - Click any student to see detailed activity
   - Real-time updates every 5 seconds

5. **End all sessions**:
   - Click "End All Sessions" button
   - Enter secret key: `80085`
   - All active sessions end immediately

---

## 📦 Building the Agent Package

To create the `.deb` installer file:

```bash
cd Lab_guardian
chmod +x build_deb.sh
./build_deb.sh
```

This creates: `build/deb/lab-guardian-agent-2.0.0.deb`

The package includes:
- ✅ Python 3 virtual environment with all dependencies
- ✅ PyQt5 GUI
- ✅ All monitoring modules
- ✅ System-wide `lab-guardian` command
- ✅ Desktop application entry
- ✅ Automatic configuration

---

## 🗄️ Database Schema

### Local SQLite (Student Machine)

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

### PostgreSQL (Backend Server)

Same schema as local SQLite, plus:
- `browser_history`: Centralized browser history storage
- All tables receive synced data from student agents

---

## 🔧 Configuration

### Agent Configuration

Edit `/etc/lab-guardian/config`:
```ini
BACKEND_URL=http://your-server:8000
SYNC_INTERVAL=30  # seconds
```

Environment variables:
- `LAB_GUARDIAN_API_URL`: Backend URL (default: http://localhost:8000)
- `LG_SNAPSHOT_INTERVAL`: Process snapshot interval (default: 30s)
- `LG_DELTA_INTERVAL`: Process delta interval (default: 3s)

### Backend Configuration

Create `backend/.env`:
```env
PORT=8000
DATABASE_URL=postgres://postgres:password@localhost:5432/lab_guardian
REDIS_URL=redis://localhost:6379  # Optional
```

### Frontend Configuration

Create `frontend/.env`:
```env
VITE_API_BASE=http://localhost:8000/api
```

---

## 🎯 Key Features

### Offline-First Design
- ✅ **100% offline operation** - No internet required during exam
- ✅ **Local SQLite storage** - All data saved locally first
- ✅ **Automatic sync** - Uploads when internet becomes available
- ✅ **Delta sync** - Only uploads unsynced records
- ✅ **Retry logic** - Automatically retries failed syncs

### Security Features
- ✅ **Secret key protection** - Only teacher can end sessions (key: 80085)
- ✅ **Process monitoring** - Students cannot kill the agent easily
- ✅ **Tamper-resistant** - All data logged locally with timestamps
- ✅ **No authentication needed** - Simplified for exam environment

### Monitoring Capabilities
- ✅ **Process monitoring** - All running processes with CPU/Memory
- ✅ **Browser history** - Full URLs from Chrome, Firefox, Edge, Brave
- ✅ **Terminal tracking** - Commands and network connections
- ✅ **USB device detection** - Brand names and connection times
- ✅ **Incognito detection** - Detects private browsing modes

### Teacher Dashboard
- ✅ **No login required** - Direct access for single teacher
- ✅ **Real-time updates** - Auto-refresh every 5 seconds
- ✅ **Smart grouping** - Students grouped by start time
- ✅ **Powerful filters** - Filter by lab number, time range
- ✅ **Detailed view** - Click student to see all activities
- ✅ **Session control** - End all sessions with secret key

---

## 🔍 Data Flow

### Student Starts Exam
```
1. Student enters Roll No + Lab No in UI
2. Agent creates exam session in local SQLite
3. Monitors start (process, device, network, browser)
4. All data saved to local database
5. Status indicators show: Monitoring ✅, Internet ❌, Sync ❌
```

### Data Sync (When Internet Available)
```
1. Sync Manager checks internet every 10 seconds
2. If connected, collects all unsynced records
3. Sends batch POST to /api/logs/receive
4. Backend stores in PostgreSQL
5. Local records marked as synced
6. UI shows: Sync ✅
```

### Teacher Monitoring
```
1. Dashboard polls /api/dashboard/students every 10s
2. Students grouped by start_time (descending)
3. Click student → /api/dashboard/student/:sessionId
4. Detailed activity view with auto-refresh
```

### Session Termination
```
1. Teacher clicks "End All Sessions"
2. Enters secret key: 80085
3. Backend updates all active sessions
4. Students see "Session Ended" message
5. Agent closes automatically
```

---

## 📊 API Reference

### Agent → Backend

**POST /api/logs/receive**
Receive batch of logs from student agent.

Request:
```json
{
  "session_id": "uuid",
  "timestamp": "2024-01-01T10:00:00Z",
  "processes": [...],
  "devices": [...],
  "terminal_events": [...],
  "browser_history": [...]
}
```

Response:
```json
{
  "message": "Logs received successfully",
  "totalRecords": 150,
  "session_id": "uuid"
}
```

### Dashboard Endpoints

**GET /api/dashboard/students?lab_no=L01&time_from=...&time_to=...**
Get all students grouped by start time.

**GET /api/dashboard/student/:sessionId**
Get detailed activity for a specific student.

**POST /api/exam/end-all**
End all active sessions (requires secret_key).

---

## 🧪 Testing

### Test Agent Locally
```bash
cd Lab_guardian
python3 -m lab_guardian start -vv
```

### Test Backend
```bash
cd backend
npm test
```

### Test Dashboard
Open browser to http://localhost:5173

---

## 🚨 Troubleshooting

### Agent won't start
```bash
# Check if Python 3.9+ is installed
python3 --version

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

### Dashboard not showing students
```bash
# Check backend is running
curl http://localhost:8000/api/health

# Check database connection
cd backend
npm run migrate

# View backend logs
tail -f backend/logs/*.log
```

---

##  License

MIT License - See individual component READMEs for details.

---

**Built for reliable exam monitoring in any network condition** 🎓
