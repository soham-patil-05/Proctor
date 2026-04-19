import { useState } from 'react';

function EndSessionModal({ onClose, onConfirm }) {
  const [secretKey, setSecretKey] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!secretKey.trim()) {
      setError('Please enter the secret key');
      return;
    }

    try {
      await onConfirm(secretKey);
    } catch (err) {
      setError(err.message || 'Invalid secret key');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>⚠️ End All Exam Sessions</h3>
        <p style={{ marginBottom: '1rem', color: '#6b7280' }}>
          This will end all active exam sessions. Please enter the secret key to confirm.
        </p>
        
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            className="modal-input"
            placeholder="Enter secret key..."
            value={secretKey}
            onChange={(e) => {
              setSecretKey(e.target.value);
              setError('');
            }}
            autoFocus
          />
          
          {error && (
            <div style={{ color: '#ef4444', marginBottom: '1rem', fontSize: '0.875rem' }}>
              {error}
            </div>
          )}
          
          <div className="modal-actions">
            <button
              type="button"
              className="btn-primary"
              style={{ backgroundColor: '#6b7280' }}
              onClick={onClose}
            >
              Cancel
            </button>
            <button type="submit" className="btn-danger">
              End All Sessions
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default EndSessionModal;
