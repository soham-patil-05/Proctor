export default function InputField({
  label,
  type = 'text',
  id,
  name,
  value,
  onChange,
  placeholder = '',
  required = false,
  error = '',
  disabled = false,
  className = '',
  hint = '',
  ...props
}) {
  return (
    <div className={`w-full ${className}`}>
      {label && (
        <label htmlFor={id} className="block text-xs font-semibold text-[var(--color-gray-600)] uppercase tracking-wide mb-1.5">
          {label}
          {required && <span className="text-[var(--color-error)] ml-0.5">*</span>}
        </label>
      )}
      <input
        type={type}
        id={id}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        className={`w-full px-3.5 py-2.5 rounded-lg border text-sm transition-all duration-150
          ${error
            ? 'border-[var(--color-error)] ring-1 ring-[var(--color-error)] bg-[var(--color-error-bg)]'
            : 'border-[var(--color-gray-300)] bg-white hover:border-[var(--color-gray-400)] focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-opacity-20'
          }
          focus:outline-none disabled:bg-[var(--color-gray-50)] disabled:text-[var(--color-gray-400)] disabled:cursor-not-allowed
          placeholder:text-[var(--color-gray-400)]`}
        {...props}
      />
      {hint && !error && (
        <p className="mt-1 text-xs text-[var(--color-gray-400)]">{hint}</p>
      )}
      {error && (
        <p className="mt-1 text-xs text-[var(--color-error)] flex items-center gap-1">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 4zm0 8a1 1 0 110-2 1 1 0 010 2z" />
          </svg>
          {error}
        </p>
      )}
    </div>
  );
}
