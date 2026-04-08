import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const SessionContext = createContext();

export function SessionProvider({ children }) {
  const [liveSession, setLiveSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkLiveSession();
  }, []);

  const checkLiveSession = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setLoading(false);
        return;
      }

      const sessions = await api.sessions.getAll('live');
      if (sessions && sessions.length > 0) {
        setLiveSession(sessions[0]);
      }
    } catch (error) {
      console.error('Error checking live session:', error);
    } finally {
      setLoading(false);
    }
  };

  const startSession = (session) => {
    setLiveSession(session);
  };

  const endSession = () => {
    setLiveSession(null);
  };

  const value = {
    liveSession,
    loading,
    startSession,
    endSession,
    refreshLiveSession: checkLiveSession,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}
