export default function Card({
  children,
  className = '',
  hoverable = false,
  onClick,
  ...props
}) {
  const baseClasses = 'bg-white rounded-lg shadow-[var(--shadow-md)] transition-all duration-200';
  const hoverClasses = hoverable ? 'hover:shadow-[var(--shadow-lg)] hover:-translate-y-1 cursor-pointer' : '';

  return (
    <div
      onClick={onClick}
      className={`${baseClasses} ${hoverClasses} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
