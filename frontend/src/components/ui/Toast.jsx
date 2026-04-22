import { useEffect, useState } from 'react';

let toastListeners = [];
let toastId = 0;

export function toast(message, type = 'info', duration = 3500) {
  const id = ++toastId;
  toastListeners.forEach((fn) => fn({ id, message, type }));
  return id;
}

toast.success = (msg, dur) => toast(msg, 'success', dur);
toast.error = (msg, dur) => toast(msg, 'error', dur);
toast.info = (msg, dur) => toast(msg, 'info', dur);

export function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    const handler = (t) => {
      setToasts((prev) => [...prev, t]);
      setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== t.id)), 3500);
    };
    toastListeners.push(handler);
    return () => {
      toastListeners = toastListeners.filter((fn) => fn !== handler);
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white pointer-events-auto slide-up
            ${t.type === 'success' ? 'bg-[var(--color-success)]' : t.type === 'error' ? 'bg-[var(--color-error)]' : 'bg-[var(--color-primary)]'}`}
        >
          {t.type === 'success' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"/>
            </svg>
          )}
          {t.type === 'error' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm3.28 9.72a.75.75 0 01-1.06 1.06L8 9.06l-2.22 2.72a.75.75 0 11-1.06-1.06L6.94 8 4.72 5.78a.75.75 0 011.06-1.06L8 6.94l2.22-2.22a.75.75 0 111.06 1.06L9.06 8l2.22 2.22z"/>
            </svg>
          )}
          {t.message}
        </div>
      ))}
    </div>
  );
}
