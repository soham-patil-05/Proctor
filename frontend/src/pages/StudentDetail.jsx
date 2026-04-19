import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchStudentDetails } from '../services/api';

const REFRESH_INTERVAL = 5000; // 5 seconds

function StudentDetail() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [studentData, setStudentData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('processes');

  useEffect(() => {
    loadDetails();
    const interval = setInterval(loadDetails, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [sessionId]);

  const loadDetails = async () => {
    try {
      setLoading(true);
      const data = await fetchStudentDetails(sessionId);
      setStudentData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
  };

  if (loading && !studentData) {
    return <div className="loading">Loading student details...</div>;
  }

  if (error) {
    return (
      <div>
        <button className="back-btn" onClick={() => navigate('/')}>
          ← Back to Dashboard
        </button>
        <div style={{ background: '#fee', padding: '1rem', borderRadius: '0.375rem', color: '#c00' }}>
          Error: {error}
        </div>
      </div>
    );
  }

  if (!studentData) {
    return (
      <div>
        <button className="back-btn" onClick={() => navigate('/')}>
          ← Back to Dashboard
        </button>
        <div className="empty-state">
          <h3>Student Not Found</h3>
        </div>
      </div>
    );
  }

  const { session, processes, devices, terminal_events, browser_history } = studentData;

  return (
    <div>
      <button className="back-btn" onClick={() => navigate('/')}>
        ← Back to Dashboard
      </button>

      <div className="student-detail-header">
        <h2>{session.roll_no}</h2>
        <div className="detail-meta">
          <span>📍 Lab: {session.lab_no}</span>
          <span>🕐 Started: {formatTime(session.start_time)}</span>
          {session.end_time && <span>✅ Ended: {formatTime(session.end_time)}</span>}
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'processes' ? 'active' : ''}`}
          onClick={() => setActiveTab('processes')}
        >
          💻 Processes ({processes?.length || 0})
        </button>
        <button
          className={`tab ${activeTab === 'devices' ? 'active' : ''}`}
          onClick={() => setActiveTab('devices')}
        >
          🔌 Devices ({devices?.length || 0})
        </button>
        <button
          className={`tab ${activeTab === 'terminal' ? 'active' : ''}`}
          onClick={() => setActiveTab('terminal')}
        >
          💻 Terminal ({terminal_events?.length || 0})
        </button>
        <button
          className={`tab ${activeTab === 'browser' ? 'active' : ''}`}
          onClick={() => setActiveTab('browser')}
        >
          🌐 Browser ({browser_history?.length || 0})
        </button>
      </div>

      {activeTab === 'processes' && (
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th>Process Name</th>
                <th>PID</th>
                <th>CPU %</th>
                <th>Memory (MB)</th>
                <th>Risk Level</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {processes?.map((proc) => (
                <tr key={proc.id}>
                  <td>{proc.process_name}</td>
                  <td>{proc.pid}</td>
                  <td>{parseFloat(proc.cpu_percent || 0).toFixed(1)}%</td>
                  <td>{parseFloat(proc.memory_mb || 0).toFixed(1)}</td>
                  <td className={`risk-${proc.risk_level || 'normal'}`}>
                    {(proc.risk_level || 'normal').toUpperCase()}
                  </td>
                  <td>{proc.status}</td>
                </tr>
              ))}
              {(!processes || processes.length === 0) && (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center' }}>No processes recorded</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'devices' && (
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th>Device Name</th>
                <th>Type</th>
                <th>Risk Level</th>
                <th>Connected At</th>
                <th>Disconnected At</th>
              </tr>
            </thead>
            <tbody>
              {devices?.map((device) => (
                <tr key={device.id}>
                  <td>{device.readable_name || device.device_name}</td>
                  <td>{device.device_type}</td>
                  <td className={`risk-${device.risk_level || 'normal'}`}>
                    {(device.risk_level || 'normal').toUpperCase()}
                  </td>
                  <td>{formatTime(device.connected_at)}</td>
                  <td>{device.disconnected_at ? formatTime(device.disconnected_at) : 'Still connected'}</td>
                </tr>
              ))}
              {(!devices || devices.length === 0) && (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center' }}>No devices detected</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'terminal' && (
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th>Tool</th>
                <th>Command/Connection</th>
                <th>Risk Level</th>
                <th>Type</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {terminal_events?.map((event) => (
                <tr key={event.id}>
                  <td>{event.tool}</td>
                  <td>
                    {event.full_command || `${event.remote_host || event.remote_ip}:${event.remote_port}`}
                  </td>
                  <td className={`risk-${event.risk_level || 'normal'}`}>
                    {(event.risk_level || 'normal').toUpperCase()}
                  </td>
                  <td>{event.event_type}</td>
                  <td>{formatTime(event.detected_at)}</td>
                </tr>
              ))}
              {(!terminal_events || terminal_events.length === 0) && (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center' }}>No terminal events detected</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'browser' && (
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th>URL</th>
                <th>Title</th>
                <th>Browser</th>
                <th>Visits</th>
                <th>Last Visited</th>
              </tr>
            </thead>
            <tbody>
              {browser_history?.map((entry) => (
                <tr key={entry.id}>
                  <td style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {entry.url}
                  </td>
                  <td>{entry.title || 'N/A'}</td>
                  <td>{entry.browser}</td>
                  <td>{entry.visit_count}</td>
                  <td>{formatTime(entry.last_visited)}</td>
                </tr>
              ))}
              {(!browser_history || browser_history.length === 0) && (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center' }}>No browser history recorded</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default StudentDetail;
