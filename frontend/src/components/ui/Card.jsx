export default function Card({ children, className = '', hoverable = false, onClick, ...props }) {
  const base =
    'bg-white rounded-xl border border-[var(--color-gray-200)] shadow-[var(--shadow-sm)] transition-all duration-150';
  const hover = hoverable
    ? 'hover:shadow-[var(--shadow-md)] hover:-translate-y-0.5 cursor-pointer'
    : '';

  return (
    <div onClick={onClick} className={`${base} ${hover} ${className}`} {...props}>
      {children}
    </div>
  );
}
