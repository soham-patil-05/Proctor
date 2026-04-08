import { Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import MySubjects from './pages/MySubjects';
import CreateSession from './pages/CreateSession';
import MySessions from './pages/MySessions';
import LiveSession from './pages/LiveSession';
import StudentDetails from './pages/StudentDetails';

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

export const routes = [
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '/register',
    element: <Register />,
  },
  {
    path: '/dashboard',
    element: (
      <ProtectedRoute>
        <Dashboard />
      </ProtectedRoute>
    ),
  },
  {
    path: '/subjects',
    element: (
      <ProtectedRoute>
        <MySubjects />
      </ProtectedRoute>
    ),
  },
  {
    path: '/create-session',
    element: (
      <ProtectedRoute>
        <CreateSession />
      </ProtectedRoute>
    ),
  },
  {
    path: '/sessions',
    element: (
      <ProtectedRoute>
        <MySessions />
      </ProtectedRoute>
    ),
  },
  {
    path: '/live-session/:sessionId',
    element: (
      <ProtectedRoute>
        <LiveSession />
      </ProtectedRoute>
    ),
  },
  {
    path: '/student/:rollNo',
    element: (
      <ProtectedRoute>
        <StudentDetails />
      </ProtectedRoute>
    ),
  },
  {
    path: '/',
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
];
