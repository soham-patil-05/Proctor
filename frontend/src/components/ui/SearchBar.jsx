import { Search } from 'lucide-react';
import { useState, useEffect } from 'react';

export default function SearchBar({
  placeholder = 'Search...',
  onSearch,
  debounce = 300,
  className = '',
  ...props
}) {
  const [value, setValue] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(value);
    }, debounce);

    return () => clearTimeout(timer);
  }, [value, debounce, onSearch]);

  return (
    <div className={`relative ${className}`}>
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <Search className="h-5 w-5 text-[var(--color-gray-400)]" />
      </div>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--color-gray-300)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:border-transparent transition-all duration-200"
        {...props}
      />
    </div>
  );
}
