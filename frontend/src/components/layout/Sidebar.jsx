import { Home, BookOpen, Plus, List } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();

  const menuItems = [
    { path: '/dashboard', label: 'Dashboard', icon: Home },
    { path: '/subjects', label: 'My Subjects', icon: BookOpen },
    { path: '/create-session', label: 'Create Session', icon: Plus },
    { path: '/sessions', label: 'My Sessions', icon: List },
  ];

  return (
    <aside className="w-64 bg-[var(--color-primary)] text-white min-h-screen fixed left-0 top-0 shadow-xl">
      <div className="p-6">
        <div className="flex items-center space-x-3 mb-8">
          <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center">
            <span className="text-[var(--color-primary)] font-bold text-xl">L</span>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-wide">Lab Monitor</h1>
            <p className="text-xs text-[var(--color-primary-light)]">Teacher Portal</p>
          </div>
        </div>

        <nav className="space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-white text-[var(--color-primary)] shadow-md'
                    : 'text-white hover:bg-[var(--color-primary-light)] hover:translate-x-1'
                }`}
              >
                <Icon className="h-5 w-5" />
                <span className="font-medium">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
