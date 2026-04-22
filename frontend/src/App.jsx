import { BrowserRouter, useRoutes } from 'react-router-dom';
import { routes } from './routes';
import { ToastContainer } from './components/ui/Toast';

function AppRoutes() {
  return useRoutes(routes);
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
      <ToastContainer />
    </BrowserRouter>
  );
}

export default App;
