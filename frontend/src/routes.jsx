import { Navigate } from 'react-router-dom';
import ExamDashboard from './pages/ExamDashboard';
import StudentActivity from './pages/StudentActivity';

// No authentication required for offline-first architecture
export const routes = [
  {
    path: '/',
    element: <ExamDashboard />,
  },
  {
    path: '/student/:sessionId',
    element: <StudentActivity />,
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
];
