# Teacher Lab Monitoring System

A comprehensive teacher-facing Single Page Application (SPA) for monitoring and managing lab sessions with real-time student activity tracking.

## Features

- **Authentication**: Secure login system with Bearer token authentication
- **Dashboard**: Overview of subjects, sessions, and live session status
- **Subject Management**: Create and manage subjects with department and year information
- **Session Management**: Create, monitor, and end lab sessions
- **Live Student Monitoring**: Real-time tracking of student activities with virtualized list for performance
- **Student Details**: Detailed view with WebSocket-powered live process monitoring, device tracking, and network information
- **Responsive Design**: Professional college aesthetic with navy blue theme

## Technology Stack

- **Frontend Framework**: React 18 with Vite
- **Routing**: React Router DOM
- **Styling**: Tailwind CSS with custom design tokens
- **Real-time Communication**: WebSocket with automatic reconnection
- **UI Components**: Custom component library with accessible, reusable components
- **Performance**: React Window for virtualized lists

## Environment Setup

The application requires the following environment variables to be set in `.env`:

```
VITE_API_BASE=https://localhost:8000/api
VITE_WS_BASE=wss://localhost:8000
```

These are already configured in the `.env` file.

## Backend Requirements

The application expects a backend server running at `https://localhost:8000` with the following endpoints:

### Authentication
- `POST /api/auth/login` - User login

### Subjects
- `GET /api/teacher/subjects` - Get all subjects
- `POST /api/teacher/subjects` - Create new subject

### Sessions
- `POST /api/teacher/sessions` - Create new session
- `GET /api/teacher/sessions?status={all|live|ended}` - Get sessions
- `GET /api/teacher/sessions/:sessionId` - Get session details
- `POST /api/teacher/sessions/:sessionId/end` - End session
- `GET /api/teacher/sessions/:sessionId/students` - Get session students

### Students
- `GET /api/teacher/students/:rollNo` - Get student details
- `GET /api/teacher/students/:rollNo/devices` - Get student devices
- `GET /api/teacher/students/:rollNo/network` - Get student network info

### WebSocket
- `wss://localhost:8000/ws/sessions/:sessionId/students/:rollNo/processes` - Live process monitoring

## Installation

```bash
npm install
```

## Development

```bash
npm run dev
```

The development server will start. Note: The backend server must be running at `https://localhost:8000` for the application to function properly.

## Build

```bash
npm run build
```

This will create a production build in the `dist` directory.

## Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── assets/              # Static assets (logos, icons)
├── components/
│   ├── layout/         # Layout components (Sidebar, Topbar, LiveSessionBanner)
│   ├── ui/             # Reusable UI components (Button, Card, Modal, etc.)
│   └── session/        # Session-specific components
├── pages/              # Page components
│   ├── Login.jsx
│   ├── Dashboard.jsx
│   ├── MySubjects.jsx
│   ├── CreateSession.jsx
│   ├── MySessions.jsx
│   ├── LiveSession.jsx
│   └── StudentDetails.jsx
├── services/
│   ├── api.js          # HTTPS API service
│   └── socket.js       # WebSocket service with reconnection
├── context/
│   └── SessionContext.jsx  # Session state management
├── styles/
│   └── tokens.css      # Design tokens and theme variables
├── App.jsx             # Main app component with routing
└── routes.jsx          # Route definitions
```

## Key Features Implementation

### Authentication
- Token-based authentication stored in localStorage
- Protected routes with automatic redirect to login
- Automatic logout on 401 responses

### Live Session Banner
- Persistent banner displayed across all pages when a session is active
- Click to resume session
- Pulse animation for visual feedback

### Student List Virtualization
- React Window for efficient rendering of large student lists
- Debounced search (300ms) for filtering by roll number
- Smooth scrolling and hover effects

### WebSocket Connection
- Automatic connection on Student Details page
- Reconnection logic with exponential backoff
- Heartbeat monitoring (10s timeout)
- Visual connection status indicators
- Process event handling: snapshot, new, update, end

### Real-time Process Monitoring
- Flash highlight for new processes
- CPU increase detection (>30%) with visual feedback
- Graceful handling of ended processes
- Update throttling for performance

## Design System

### Colors
- **Primary**: Navy blue (#0a2540)
- **Secondary**: Gray tones
- **Accent**: Blue (#2563eb)
- **Success**: Green (#10b981)
- **Warning**: Orange (#f59e0b)
- **Error**: Red (#ef4444)

### Spacing
- 8px base unit system
- Consistent padding and margins

### Transitions
- Fast: 200ms (hover effects)
- Medium: 300ms (page transitions)
- Smooth ease-in-out timing

### Typography
- Sans-serif font stack
- Bold headings with increased letter spacing
- Line height: 150% for body, 120% for headings

## Browser Support

Modern browsers with ES2020+ support:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Security Considerations

- HTTPS-only API communication
- Bearer token authentication
- Secure WebSocket (WSS) connections
- Protected routes with authentication checks
- Automatic token validation and logout

## Performance Optimizations

- Virtualized student lists for large datasets
- Debounced search inputs
- Memoized components to prevent unnecessary re-renders
- Efficient WebSocket event handling
- Code splitting with React lazy loading potential

## Accessibility

- WCAG AA compliant color contrast
- Keyboard navigation support
- ARIA labels for interactive elements
- Focus indicators for all focusable elements
- Semantic HTML structure

## License

Proprietary - College Lab Monitoring System
