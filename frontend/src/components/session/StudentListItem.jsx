import { memo } from 'react';
import { ChevronRight } from 'lucide-react';

const StudentListItem = memo(({ student, onClick, style }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'normal':
        return 'bg-[var(--color-success)]';
      case 'warning':
        return 'bg-[var(--color-warning)]';
      case 'error':
        return 'bg-[var(--color-error)]';
      default:
        return 'bg-[var(--color-gray-400)]';
    }
  };

  const formatLastSeen = (lastSeen) => {
    if (!lastSeen) return 'Never';
    const date = new Date(lastSeen);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins === 1) return '1 min ago';
    if (diffMins < 60) return `${diffMins} mins ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours === 1) return '1 hour ago';
    return `${diffHours} hours ago`;
  };

  return (
    <div
      style={style}
      onClick={() => onClick(student)}
      className="px-6 py-4 bg-white border-b border-[var(--color-gray-200)] hover:bg-[var(--color-gray-50)] hover:scale-[1.01] transition-all duration-200 cursor-pointer"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4 flex-1">
          <div className={`w-3 h-3 rounded-full ${getStatusColor(student.status)}`}></div>
          <div className="flex-1">
            <div className="flex items-center space-x-3">
              <span className="font-semibold text-[var(--color-gray-900)]">
                {student.rollNo}
              </span>
              <span className="text-[var(--color-gray-600)]">{student.name}</span>
            </div>
            <div className="text-sm text-[var(--color-gray-500)] mt-0.5">
              Last seen: {formatLastSeen(student.lastSeen)}
            </div>
          </div>
        </div>
        <ChevronRight className="h-5 w-5 text-[var(--color-gray-400)]" />
      </div>
    </div>
  );
});

StudentListItem.displayName = 'StudentListItem';

export default StudentListItem;
