import { useState, useEffect } from 'react';
import { BookOpen, Activity, List } from 'lucide-react';
import { api } from '../services/api';
import Card from '../components/ui/Card';
import Sidebar from '../components/layout/Sidebar';
import Topbar from '../components/layout/Topbar';
import { useSession } from '../context/SessionContext';

export default function Dashboard() {
  const [stats, setStats] = useState({
    totalSubjects: 0,
    totalSessions: 0,
  });
  const [loading, setLoading] = useState(true);
  const teacherName = localStorage.getItem('teacherName') || 'Professor';
  const { liveSession } = useSession();

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const [subjects, sessions] = await Promise.all([
        api.subjects.getAll(),
        api.sessions.getAll('all'),
      ]);

      setStats({
        totalSubjects: subjects.length,
        totalSessions: sessions.length,
      });
    } catch (error) {
      console.error('Error loading stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      title: 'Total Subjects',
      value: stats.totalSubjects,
      icon: BookOpen,
      color: 'var(--color-accent)',
    },
    {
      title: 'Active Session',
      value: liveSession ? '1' : '0',
      icon: Activity,
      color: 'var(--color-success)',
    },
    {
      title: 'Total Sessions',
      value: stats.totalSessions,
      icon: List,
      color: 'var(--color-primary)',
    },
  ];

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      <Sidebar />
      <div className="ml-64">
        <Topbar teacherName={teacherName} />
        <main className={`p-8 ${liveSession ? 'mt-28' : 'mt-16'}`}>
          <div className="max-w-7xl mx-auto">
            <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-8 tracking-wide">
              Dashboard
            </h1>

            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[1, 2, 3].map((i) => (
                  <Card key={i} className="p-6 animate-pulse">
                    <div className="h-4 bg-[var(--color-gray-200)] rounded w-1/2 mb-4"></div>
                    <div className="h-8 bg-[var(--color-gray-200)] rounded w-1/3"></div>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {statCards.map((stat, index) => {
                  const Icon = stat.icon;
                  return (
                    <Card
                      key={index}
                      className="p-6 fade-in"
                      style={{ animationDelay: `${index * 100}ms` }}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-[var(--color-gray-600)] mb-2">
                            {stat.title}
                          </p>
                          <p className="text-4xl font-bold text-[var(--color-gray-900)]">
                            {stat.value}
                          </p>
                        </div>
                        <div
                          className="w-14 h-14 rounded-xl flex items-center justify-center"
                          style={{ backgroundColor: `${stat.color}20` }}
                        >
                          <Icon
                            className="h-7 w-7"
                            style={{ color: stat.color }}
                          />
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}

            <div className="mt-12">
              <Card className="p-8">
                <h2 className="text-xl font-bold text-[var(--color-gray-900)] mb-4">
                  Welcome to Lab Monitoring System
                </h2>
                <p className="text-[var(--color-gray-600)] leading-relaxed">
                  Monitor and manage your lab sessions effectively. Create new sessions,
                  track student activities, and view real-time process information.
                </p>
              </Card>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
