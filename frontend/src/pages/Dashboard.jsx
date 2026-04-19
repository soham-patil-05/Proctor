import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchDashboardStudents, endAllSessions } from '../services/api';
import EndSessionModal from '../components/EndSessionModal';

const REFRESH_INTERVAL = 5000; // 5 seconds

function Dashboard() {
  const navigate = useNavigate();
  const [students, setStudents] = useState([]);
  const [groupedStudents, setGroupedStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    lab_no: '',
    time_from: '',
    time_to: '',
  });
  const [showEndModal, setShowEndModal] = useState(false);

  const loadStudents = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchDashboardStudents(filters);
      setStudents(data);
      setGroupedStudents(data.grouped || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadStudents();
    const interval = setInterval(loadStudents, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [loadStudents]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleEndSessions = async (secretKey) => {
    try {
      await endAllSessions(secretKey);
      setShowEndModal(false);
      alert('All sessions ended successfully!');
      loadStudents(); // Refresh the list
    } catch (err) {
      alert(err.message);
      throw err; // Re-throw to keep modal open
    }
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString();
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
  };

  if (loading && groupedStudents.length === 0) {
    return <div className="loading">Loading students...</div>;
  }

  return (
    <div>
      <div className="dashboard-header">
        <h2>Active Exam Sessions</h2>
        <div className="filters">
          <select
            className="filter-select"
            value={filters.lab_no}
            onChange={(e) => handleFilterChange('lab_no', e.target.value)}
          >
            <option value="">All Labs</option>
            {Array.from({ length: 12 }, (_, i) => `L${(i + 1).toString().padStart(2, '0')}`).map(lab => (
              <option key={lab} value={lab}>{lab}</option>
            ))}
          </select>
          
          <input
            type="datetime-local"
            className="filter-input"
            value={filters.time_from}
            onChange={(e) => handleFilterChange('time_from', e.target.value)}
            placeholder="From"
          />
          
          <input
            type="datetime-local"
            className="filter-input"
            value={filters.time_to}
            onChange={(e) => handleFilterChange('time_to', e.target.value)}
            placeholder="To"
          />
          
          <button className="btn-danger" onClick={() => setShowEndModal(true)}>
            End All Sessions
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: '#fee', padding: '1rem', borderRadius: '0.375rem', marginBottom: '1rem', color: '#c00' }}>
          Error: {error}
        </div>
      )}

      {groupedStudents.length === 0 ? (
        <div className="empty-state">
          <h3>No Active Sessions</h3>
          <p>Students will appear here when they start their exams.</p>
        </div>
      ) : (
        <div className="student-groups">
          {groupedStudents.map((group, index) => (
            <div key={index} className="student-group">
              <div className="group-header">
                Started at {formatDate(group.start_time)} ({group.students.length} student{group.students.length !== 1 ? 's' : ''})
              </div>
              <div className="student-list">
                {group.students.map((student) => (
                  <div
                    key={student.session_id}
                    className="student-card"
                    onClick={() => navigate(`/student/${student.session_id}`)}
                  >
                    <div className="student-info">
                      <h3>{student.roll_no}</h3>
                      <div className="student-meta">
                        <span>📍 Lab: {student.lab_no}</span>
                        <span>🕐 Started: {formatTime(student.start_time)}</span>
                      </div>
                    </div>
                    <div className="student-stats">
                      <span className="stat-badge">💻 {student.process_count || 0} processes</span>
                      <span className="stat-badge">🔌 {student.device_count || 0} devices</span>
                      <span className="stat-badge">💻 {student.terminal_event_count || 0} terminal</span>
                      <span className="stat-badge">🌐 {student.browser_history_count || 0} URLs</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {showEndModal && (
        <EndSessionModal
          onClose={() => setShowEndModal(false)}
          onConfirm={handleEndSessions}
        />
      )}
    </div>
  );
}

export default Dashboard;
