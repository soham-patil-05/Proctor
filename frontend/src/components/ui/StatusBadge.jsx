export default function StatusBadge({ status, variant, className = '' }) {
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
    dangerous: {
      color: 'bg-[#FDECEA] text-[#C62828]',
      label: 'dangerous',
      dot: 'bg-[#C62828]'
    },
    suspicious: {
      color: 'bg-[#FFF8E1] text-[#F57F17]',
      label: 'suspicious',
      dot: 'bg-[#F57F17]'
    },
    safe: {
      color: 'bg-[#E8F5E9] text-[#2E7D32]',
      label: 'safe',
      dot: 'bg-[#2E7D32]'
    },
    high: {
      color: 'bg-[#FDECEA] text-[#C62828]',
      label: 'high',
      dot: 'bg-[#C62828]'
    },
    medium: {
      color: 'bg-[#FFF8E1] text-[#F57F17]',
      label: 'medium',
      dot: 'bg-[#F57F17]'
    },
    low: {
      color: 'bg-[#E8F5E9] text-[#2E7D32]',
      label: 'low',
      dot: 'bg-[#2E7D32]'
    },
  };

  const key = variant || status;
  const config = statusConfig[key] || statusConfig.normal;

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${config.color} ${className}`}>
      <span className={`w-2 h-2 rounded-full ${config.dot} mr-1.5`}></span>
      {config.label}
    </span>
  );
}
