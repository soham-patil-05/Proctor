export default function StatusBadge({ status, className = '' }) {
  const statusConfig = {
    normal: {
      color: 'bg-[var(--color-success)] text-white',
      label: 'Normal',
      dot: 'bg-[var(--color-success)]'
    },
    warning: {
      color: 'bg-[var(--color-warning)] text-white',
      label: 'Warning',
      dot: 'bg-[var(--color-warning)]'
    },
    error: {
      color: 'bg-[var(--color-error)] text-white',
      label: 'Error',
      dot: 'bg-[var(--color-error)]'
    },
    live: {
      color: 'bg-[var(--color-success)] text-white',
      label: 'Live',
      dot: 'bg-[var(--color-success)]'
    },
    ended: {
      color: 'bg-[var(--color-gray-400)] text-white',
      label: 'Ended',
      dot: 'bg-[var(--color-gray-400)]'
    },
    active: {
      color: 'bg-[var(--color-success)] text-white',
      label: 'Active',
      dot: 'bg-[var(--color-success)]'
    },
    inactive: {
      color: 'bg-[var(--color-gray-400)] text-white',
      label: 'Inactive',
      dot: 'bg-[var(--color-gray-400)]'
    },
  };

  const config = statusConfig[status] || statusConfig.normal;

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${config.color} ${className}`}>
      <span className={`w-2 h-2 rounded-full ${config.dot} mr-1.5`}></span>
      {config.label}
    </span>
  );
}
