import { LogOut, User, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../../context/SessionContext';

export default function Topbar({ teacherName = 'Professor', hideBanner = false }) {
  const navigate = useNavigate();
  const { liveSession, endSession } = useSession();

  const handleLogout = () => {
    localStorage.clear();
    endSession();
    navigate('/login');
  };

  const showBanner = !hideBanner && !!liveSession;

  return (
    <header className="bg-white shadow-[var(--shadow-sm)] fixed top-0 right-0 left-64 z-[var(--z-index-sticky)]">
      {/* Main row: welcome + logout */}
      <div className="h-16 flex items-center justify-between px-8">
        <div className="flex items-center space-x-3">
          <User className="h-5 w-5 text-[var(--color-gray-600)]" />
          <span className="text-lg text-[var(--color-gray-900)]">
            Welcome, <span className="font-semibold">{teacherName}</span>
          </span>
        </div>

        <button
          onClick={handleLogout}
          className="flex items-center space-x-2 px-4 py-2 text-[var(--color-gray-700)] hover:text-[var(--color-error)] hover:bg-[var(--color-gray-100)] rounded-lg transition-all duration-200"
        >
          <LogOut className="h-5 w-5" />
          <span className="font-medium">Logout</span>
        </button>
      </div>

      {/* Live session banner row */}
      {showBanner && (
        <div
          onClick={() => navigate(`/live-session/${liveSession.sessionId}`)}
          className="bg-[var(--color-success)] text-white px-6 py-3 cursor-pointer hover:bg-[var(--color-success-light)] transition-all duration-200"
        >
          <div className="flex items-center justify-center space-x-3">
            <Activity className="h-5 w-5 pulse" />
            <span className="font-medium">
              Live Session Active: {liveSession.subject} - {liveSession.batch}
            </span>
            <span className="text-sm opacity-90">(Click to resume)</span>
          </div>
        </div>
      )}
    </header>
  );
}
