import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Wifi, Shield, ShieldAlert, Globe, Usb, Terminal, Activity, Code, History } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';

const API_BASE = import.meta.env.VITE_API_BASE;

// Risk config
const RISK_CONFIG = {
  high: { bg: 'bg-red-500', text: 'text-red-500', label: 'High Risk' },
  medium: { bg: 'bg-yellow-500', text: 'text-yellow-500', label: 'Warning' },
  low: { bg: 'bg-green-500', text: 'text-green-500', label: 'Safe' },
  normal: { bg: 'bg-green-500', text: 'text-green-500', label: 'Normal' },
};

function RiskBadge({ level }) {
  const cfg = RISK_CONFIG[level] || RISK_CONFIG.normal;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-opacity-15 ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.bg}`}></span>
      {cfg.label}
    </span>
  );
}

export default function StudentActivity() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  
  const [sessionData, setSessionData] = useState(null);
  const [processes, setProcesses] = useState([]);
  const [devices, setDevices] = useState([]);
  const [terminalEvents, setTerminalEvents] = useState([]);
  const [browserHistory, setBrowserHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('processes');
  const [refreshInterval, setRefreshInterval] = useState(null);

  const TABS = [
    { key: 'processes', label: 'Processes', icon: Terminal },
    { key: 'browser', label: 'Browser History', icon: History },
    { key: 'terminal', label: 'Terminal', icon: Code },
    { key: 'devices', label: 'Devices', icon: Usb },
  ];

  // Fetch student data
  const fetchStudentData = async () => {
    try {
      const response = await fetch(`${API_BASE}/dashboard/student/${sessionId}`);
      const data = await response.json();
      
      setSessionData(data.session);
      setProcesses(data.processes || []);
      setDevices(data.devices || []);
      setTerminalEvents(data.terminal_events || []);
      setBrowserHistory(data.browser_history || []);
    } catch (error) {
      console.error('Error fetching student data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStudentData();

    // Auto-refresh every 5 seconds
    setRefreshInterval(setInterval(fetchStudentData, 5000));

    return () => {
      if (refreshInterval) clearInterval(refreshInterval);
    };
  }, [sessionId]);

  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString();
  };

  const getDuration = () => {
    if (!sessionData?.start_time) return '-';
    const endTime = sessionData.end_time || Date.now() / 1000;
    const elapsed = endTime - sessionData.start_time;
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const seconds = Math.floor(elapsed % 60);
    return `${hours}h ${minutes}m ${seconds}s`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading student activity...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" onClick={() => navigate('/')}>
                <ArrowLeft className="h-5 w-5 mr-2" />
                Back to Dashboard
              </Button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {sessionData?.roll_no}
                </h1>
                <p className="text-sm text-gray-600">
                  Lab: {sessionData?.lab_no} • Duration: {getDuration()}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Wifi className="h-5 w-5 text-green-500" />
              <span className="text-sm font-medium text-green-600">
                {sessionData?.end_time ? 'Ended' : 'Active'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Tab Bar */}
        <div className="mb-6 flex gap-2 border-b border-gray-200">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.key;
            const TabIcon = tab.icon;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <TabIcon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <Card className="p-6">
          {/* Processes Tab */}
          {activeTab === 'processes' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Running Processes</h2>
                <span className="text-sm text-gray-500">({processes.length})</span>
              </div>
              {processes.length === 0 ? (
                <div className="text-center py-10">
                  <Activity className="h-10 w-10 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500">No processes recorded</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {processes.map((proc, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100"
                    >
                      <div>
                        <p className="font-semibold text-sm">{proc.process_name}</p>
                        <p className="text-xs text-gray-500">
                          PID: {proc.pid} • CPU: {proc.cpu_percent}% • Mem: {proc.memory_mb} MB
                        </p>
                      </div>
                      <RiskBadge level={proc.risk_level || 'normal'} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Browser History Tab */}
          {activeTab === 'browser' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Browser History</h2>
                <span className="text-sm text-gray-500">({browserHistory.length})</span>
              </div>
              {browserHistory.length === 0 ? (
                <div className="text-center py-10">
                  <Globe className="h-10 w-10 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500">No browsing activity</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {browserHistory.map((entry, idx) => (
                    <div key={idx} className="p-3 rounded-lg bg-gray-50">
                      <p className="text-sm font-medium truncate">{entry.title || entry.url}</p>
                      <p className="text-xs text-blue-600 truncate">{entry.url}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                        <span>{entry.browser}</span>
                        <span>•</span>
                        <span>{entry.visit_count} visits</span>
                        <span>•</span>
                        <span>{formatTime(entry.last_visited)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Terminal Tab */}
          {activeTab === 'terminal' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Terminal Activity</h2>
                <span className="text-sm text-gray-500">({terminalEvents.length})</span>
              </div>
              {terminalEvents.length === 0 ? (
                <div className="text-center py-10">
                  <Code className="h-10 w-10 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500">No terminal activity</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {terminalEvents.map((event, idx) => (
                    <div key={idx} className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-sm">{event.tool}</span>
                        <RiskBadge level={event.risk_level || 'medium'} />
                      </div>
                      <p className="text-sm font-mono bg-white p-2 rounded border">
                        {event.full_command || `${event.remote_ip}:${event.remote_port}`}
                      </p>
                      <p className="text-xs text-gray-500 mt-2">{formatTime(event.detected_at)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Devices Tab */}
          {activeTab === 'devices' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">USB Devices</h2>
                <span className="text-sm text-gray-500">({devices.length})</span>
              </div>
              {devices.length === 0 ? (
                <div className="text-center py-10">
                  <Usb className="h-10 w-10 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500">No USB devices connected</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {devices.map((device, idx) => (
                    <div key={idx} className="flex items-center justify-between p-4 rounded-lg bg-gray-50">
                      <div>
                        <p className="font-semibold text-sm">{device.readable_name || device.device_name}</p>
                        <p className="text-xs text-gray-500">
                          {device.device_type} • {formatTime(device.connected_at)}
                        </p>
                      </div>
                      <span className="text-xs text-gray-500">
                        {device.disconnected_at ? 'Disconnected' : 'Connected'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
