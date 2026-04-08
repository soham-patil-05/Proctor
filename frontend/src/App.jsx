import { BrowserRouter, useRoutes } from 'react-router-dom';
import { SessionProvider } from './context/SessionContext';
import { routes } from './routes';

function AppRoutes() {
  return useRoutes(routes);
}

function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <AppRoutes />
      </SessionProvider>
    </BrowserRouter>
  );
}

export default App;
