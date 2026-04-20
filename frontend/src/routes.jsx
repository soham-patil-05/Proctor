import FilterPage from './pages/FilterPage';
import StudentDetailPage from './pages/StudentDetailPage';

export const routes = [
  { path: '/', element: <FilterPage /> },
  { path: '/student/:rollNo', element: <StudentDetailPage /> },
];
