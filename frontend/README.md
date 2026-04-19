# Lab Guardian - Teacher Dashboard

A simple, no-login React dashboard for monitoring offline-first exam sessions.

## Features

- ✅ **No authentication required** - Direct access for teachers
- ✅ **Auto-refresh** - Updates every 5 seconds via HTTP polling
- ✅ **Student grouping** - Students grouped by start time
- ✅ **Filters** - Filter by lab number and time range
- ✅ **Detailed view** - Click student to see all activity
- ✅ **End sessions** - Secret key protected session termination

## Tech Stack

- React 18
- Vite 5
- React Router 6
- Vanilla CSS (no frameworks)

## Setup

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Configure environment

Edit `.env` file:

```env
VITE_API_BASE=http://localhost:8000
```

### 3. Start development server

```bash
npm run dev
```

Dashboard opens at: http://localhost:5173

### 4. Build for production

```bash
npm run build
```

Production files will be in `dist/` folder.

### 5. Preview production build

```bash
npm run preview
```

## Usage

### Dashboard View

1. **View active students** - Students appear automatically as they start exams
2. **Filter by lab** - Use the dropdown to filter by lab number (L01-L12)
3. **Filter by time** - Use date pickers to filter by time range
4. **Click student card** - View detailed activity for that student

### Student Detail View

- **Processes Tab** - All running processes with risk levels
- **Devices Tab** - USB/external device connections
- **Terminal Tab** - Terminal commands and network connections
- **Browser Tab** - Visited URLs and browser history

### End All Sessions

1. Click "End All Sessions" button
2. Enter secret key: `80085`
3. Click "End All Sessions" to confirm
4. All active sessions will be terminated

## API Endpoints Used

- `GET /api/dashboard/students` - Get all active students
- `GET /api/dashboard/student/:sessionId` - Get student details
- `POST /api/exam/end-all` - End all sessions

## Auto-Refresh

The dashboard automatically refreshes data every 5 seconds to show real-time updates from student agents.

## Project Structure

```
frontend/
├── src/
│   ├── main.jsx                    # Entry point
│   ├── App.jsx                     # Main app with routing
│   ├── index.css                   # Global styles
│   ├── services/
│   │   └── api.js                  # API service functions
│   ├── pages/
│   │   ├── Dashboard.jsx           # Main dashboard page
│   │   └── StudentDetail.jsx       # Student detail page
│   └── components/
│       └── EndSessionModal.jsx     # End session modal
├── index.html
├── vite.config.js
├── package.json
└── .env
```

## Deployment

### Option 1: Static Hosting

Build the project and serve the `dist/` folder with any static web server:

```bash
npm run build
# Serve dist/ folder with nginx, apache, etc.
```

### Option 2: Node.js Server

Use a simple Node.js server to serve the built files:

```bash
npm run build
npx serve dist
```

### Option 3: Behind Backend Proxy

Configure your backend (Node.js/Express) to serve the built frontend:

```javascript
// In backend server.js
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Serve frontend build in production
if (process.env.NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, '../frontend/dist')));
  
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/dist/index.html'));
  });
}
```

## Troubleshooting

### Dashboard not showing students

1. Check backend is running: `curl http://localhost:8000/api/health`
2. Check `.env` file has correct `VITE_API_BASE`
3. Check browser console for errors

### API requests failing

1. Ensure backend is on port 8000
2. Check CORS settings in backend
3. Use Vite proxy (already configured in `vite.config.js`)

### Build errors

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## License

MIT
