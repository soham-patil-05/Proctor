import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Clock } from 'lucide-react';
import { api } from '../services/api';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import Sidebar from '../components/layout/Sidebar';
import Topbar from '../components/layout/Topbar';
import { useSession } from '../context/SessionContext';

export default function MySessions() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const teacherName = localStorage.getItem('teacherName') || 'Professor';
  const { liveSession } = useSession();

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const data = await api.sessions.getAll('all');
      setSessions(data);
    } catch (error) {
      console.error('Error loading sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      <Sidebar />
      <div className="ml-64">
        <Topbar teacherName={teacherName} />
        <main className={`p-8 ${liveSession ? 'mt-28' : 'mt-16'}`}>
          <div className="max-w-7xl mx-auto">
            <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-8 tracking-wide">
              My Sessions
            </h1>

            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <Card key={i} className="p-6 animate-pulse">
                    <div className="h-4 bg-[var(--color-gray-200)] rounded w-1/3 mb-3"></div>
                    <div className="h-3 bg-[var(--color-gray-200)] rounded w-1/4"></div>
                  </Card>
                ))}
              </div>
            ) : sessions.length === 0 ? (
              <Card className="p-12 text-center">
                <p className="text-[var(--color-gray-600)] mb-4">
                  No sessions found. Create your first session to get started.
                </p>
                <Button
                  variant="primary"
                  onClick={() => navigate('/create-session')}
                >
                  Create Session
                </Button>
              </Card>
            ) : (
              <div className="space-y-4">
                {sessions.map((session, index) => (
                  <Card
                    key={session.sessionId}
                    className="p-6 fade-in"
                    hoverable
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-3">
                          <h3 className="text-xl font-bold text-[var(--color-gray-900)]">
                            {session.subject}
                          </h3>
                          <StatusBadge status={session.status} />
                        </div>
                        <div className="flex items-center space-x-6 text-sm text-[var(--color-gray-600)]">
                          <div className="flex items-center space-x-2">
                            <span className="font-medium">Batch:</span>
                            <span>{session.batch}</span>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Calendar className="h-4 w-4" />
                            <span>{formatDate(session.date)}</span>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Clock className="h-4 w-4" />
                            <span>{session.startTime}</span>
                          </div>
                        </div>
                      </div>
                      <div>
                        {session.status === 'live' ? (
                          <Button
                            variant="accent"
                            onClick={() => navigate(`/live-session/${session.sessionId}`)}
                          >
                            Resume Session
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            onClick={() => navigate(`/live-session/${session.sessionId}`)}
                          >
                            View Details
                          </Button>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
