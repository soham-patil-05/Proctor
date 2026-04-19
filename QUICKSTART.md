# Quick Start Guide - Lab Guardian

Get your offline-first exam monitoring system up and running in 5 minutes!

---

## Prerequisites

- **Node.js** ≥ 18 ([Download](https://nodejs.org/))
- **PostgreSQL** ≥ 14 ([Download](https://www.postgresql.org/download/))
- **Python** ≥ 3.9 (for student agent)

---

## 1. Setup Backend Server

```bash
# Navigate to backend
cd backend

# Install dependencies
npm install

# Create database
createdb lab_guardian
# OR on Windows with pgAdmin, create a database named "lab_guardian"

# Create .env file
echo "DATABASE_URL=postgres://postgres:YOUR_PASSWORD@localhost:5432/lab_guardian" > .env
echo "PORT=8000" >> .env

# Run database migrations
npm run migrate

# Start backend server
npm run dev
```

✅ Backend running at: **http://localhost:8000**

---

## 2. Setup Teacher Dashboard

Open a **new terminal**:

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

✅ Dashboard running at: **http://localhost:5173**

---

## 3. Setup Student Agent (on each student machine)

```bash
# Navigate to agent
cd Lab_guardian

# Run setup script (Linux/Ubuntu)
sudo bash setup.sh

# OR without auditd
bash setup.sh --no-auditd

# Start the agent
python3 -m lab_guardian start

# Or with custom backend URL
python3 -m lab_guardian start --api-url http://YOUR_SERVER_IP:8000 -vv
```

✅ Agent UI opens → Enter Roll No + Lab No → Click "Start Exam Session"

---

## 4. Test the System

1. **Open Dashboard**: http://localhost:5173
2. **Start Agent**: Enter details and start exam session
3. **Watch Dashboard**: Student should appear within 5-10 seconds
4. **Click Student**: View detailed activity (processes, devices, terminal, browser)

---

## Architecture Overview

```
Student Machine                     Server Machine
┌─────────────────┐                 ┌──────────────────┐
│ Lab Guardian    │                 │ Backend (Node.js)│
│ Agent (Python)  │ ───HTTP POST──→ │ Port 8000        │
│ SQLite Local DB │                 │ PostgreSQL       │
└─────────────────┘                 └────────┬─────────┘
                                             │
                                             │ GET /api/dashboard
                                             ▼
                                  ┌──────────────────┐
                                  │ Dashboard (React)│
                                  │ Port 5173        │
                                  └──────────────────┘
```

---

## Key Features

### Student Agent
- ✅ Works **100% offline** during exam
- ✅ Stores all data in local SQLite
- ✅ Auto-syncs when internet available
- ✅ Monitors: processes, USB, network, browser, terminal

### Teacher Dashboard
- ✅ **No login required** - direct access
- ✅ Auto-refreshes every 5 seconds
- ✅ Filter by lab number and time
- ✅ View detailed student activity
- ✅ End all sessions with secret key (80085)

### Backend
- ✅ Receives batch log uploads
- ✅ Stores in PostgreSQL
- ✅ Serves dashboard API
- ✅ No authentication needed

---

## Common Commands

### Backend
```bash
cd backend
npm run dev          # Start development server
npm run migrate      # Run database migrations
npm run cleanup      # Clean old data (>7 days)
```

### Dashboard
```bash
cd frontend
npm run dev          # Start development server
npm run build        # Build for production
npm run preview      # Preview production build
```

### Student Agent
```bash
cd Lab_guardian
python3 -m lab_guardian start -vv    # Start with verbose logging
./build_deb.sh                       # Build .deb package
```

---

## Troubleshooting

### Backend won't start
```bash
# Check PostgreSQL is running
pg_isready

# Check DATABASE_URL in .env
cat backend/.env

# Test database connection
psql postgres://postgres:YOUR_PASSWORD@localhost:5432/lab_guardian -c "SELECT 1"
```

### Dashboard not showing students
1. Check backend is running: http://localhost:8000/api/health
2. Check browser console for errors (F12)
3. Verify `.env` has correct `VITE_API_BASE`

### Agent won't sync
```bash
# Check internet connection
ping 8.8.8.8

# Check backend URL
cat /etc/lab-guardian/config

# View agent logs (if installed via .deb)
journalctl -f | grep lab_guardian
```

---

## Production Deployment

### 1. Build Frontend
```bash
cd frontend
npm run build
```

### 2. Serve with Backend
Add to `backend/src/server.js`:
```javascript
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Serve frontend in production
app.use(express.static(path.join(__dirname, '../frontend/dist')));

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../frontend/dist/index.html'));
});
```

### 3. Start Backend
```bash
cd backend
NODE_ENV=production npm start
```

### 4. Deploy Agent
```bash
cd Lab_guardian
./build_deb.sh
sudo dpkg -i build/deb/lab-guardian-agent-2.0.0.deb
```

---

## Next Steps

1. **Customize Monitoring**: Edit risk levels in `Lab_guardian/lab_guardian/monitor/`
2. **Add More Filters**: Extend dashboard filters in `frontend/src/pages/Dashboard.jsx`
3. **Deploy to Server**: Use Docker or PM2 for production
4. **Configure Firewall**: Only allow ports 8000 (backend) and 5173 (dashboard)

---

## Support

- Main README: [README.md](../README.md)
- Backend Docs: [backend/README.md](../backend/README.md)
- Agent Docs: [Lab_guardian/README.md](../Lab_guardian/README.md)
- Dashboard Docs: [frontend/README.md](../frontend/README.md)

---

**Happy Monitoring! 🎓**
