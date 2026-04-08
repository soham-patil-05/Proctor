import { useNavigate } from 'react-router-dom';
import { Activity } from 'lucide-react';

export default function LiveSessionBanner({ sessionId, subject, batch }) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate(`/live-session/${sessionId}`)}
      className="fixed top-0 left-64 right-0 bg-[var(--color-success)] text-white px-6 py-3 cursor-pointer z-[var(--z-index-fixed)] shadow-lg hover:bg-[var(--color-success-light)] transition-all duration-200"
    >
      <div className="flex items-center justify-center space-x-3">
        <Activity className="h-5 w-5 pulse" />
        <span className="font-medium">
          Live Session Active: {subject} - {batch}
        </span>
        <span className="text-sm opacity-90">(Click to resume)</span>
      </div>
    </div>
  );
}
