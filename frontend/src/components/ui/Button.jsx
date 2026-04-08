export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  onClick,
  type = 'button',
  disabled = false,
  loading = false,
  className = '',
  ...props
}) {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

  const variantClasses = {
    primary: 'bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-dark)] focus:ring-[var(--color-primary)] hover:scale-[1.02] active:scale-[0.98]',
    secondary: 'bg-[var(--color-gray-200)] text-[var(--color-gray-900)] hover:bg-[var(--color-gray-300)] focus:ring-[var(--color-gray-400)] hover:scale-[1.02] active:scale-[0.98]',
    accent: 'bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-light)] focus:ring-[var(--color-accent)] hover:scale-[1.02] active:scale-[0.98]',
    danger: 'bg-[var(--color-error)] text-white hover:bg-[var(--color-error-light)] focus:ring-[var(--color-error)] hover:scale-[1.02] active:scale-[0.98]',
    outline: 'border-2 border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-white focus:ring-[var(--color-primary)] hover:scale-[1.02] active:scale-[0.98]',
    ghost: 'text-[var(--color-primary)] hover:bg-[var(--color-gray-100)] focus:ring-[var(--color-gray-300)]',
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {loading ? (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      ) : null}
      {children}
    </button>
  );
}
