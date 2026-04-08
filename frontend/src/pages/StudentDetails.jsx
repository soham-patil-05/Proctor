import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, AlertCircle, Wifi, WifiOff, Shield, ShieldAlert, ShieldCheck, Globe, Usb, Monitor, Terminal, Activity, Code } from 'lucide-react';
import { api } from '../services/api';
import WebSocketService from '../services/socket';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Sidebar from '../components/layout/Sidebar';
import Topbar from '../components/layout/Topbar';

import { useSession } from '../context/SessionContext';

/* ─── Risk helpers ───────────────────────────────────────────────── */

const RISK_CONFIG = {
  high: {
    bg: 'bg-[var(--color-error)]',
    bgLight: 'bg-red-50',
    text: 'text-[var(--color-error)]',
    border: 'border-[var(--color-error)]',
    label: 'High Risk',
    dot: 'bg-[var(--color-error)]',
  },
  medium: {
    bg: 'bg-[var(--color-warning)]',
    bgLight: 'bg-amber-50',
    text: 'text-[var(--color-warning)]',
    border: 'border-[var(--color-warning)]',
    label: 'Warning',
    dot: 'bg-[var(--color-warning)]',
  },
  low: {
    bg: 'bg-[var(--color-success)]',
    bgLight: 'bg-emerald-50',
    text: 'text-[var(--color-success)]',
    border: 'border-[var(--color-success)]',
    label: 'Safe',
    dot: 'bg-[var(--color-success)]',
  },
  normal: {
    bg: 'bg-[var(--color-success)]',
    bgLight: 'bg-emerald-50',
    text: 'text-[var(--color-success)]',
    border: 'border-[var(--color-success)]',
    label: 'Normal',
    dot: 'bg-[var(--color-success)]',
  },
};

function RiskBadge({ level, className = '' }) {
  const cfg = RISK_CONFIG[level] || RISK_CONFIG.normal;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.bg} bg-opacity-15 ${cfg.text} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`}></span>
      {cfg.label}
    </span>
  );
}

function SectionHeader({ icon: Icon, title, count, rightContent }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-[var(--color-accent)]" />
        <h2 className="text-lg font-bold text-[var(--color-gray-900)]">{title}</h2>
        {count !== undefined && (
          <span className="text-sm text-[var(--color-gray-500)]">({count})</span>
        )}
      </div>
      {rightContent}
    </div>
  );
}

/* ─── Domain risk classification ─────────────────────────────────── */

const HIGH_RISK_DOMAINS = new Set([
  'chatgpt.com', 'openai.com', 'chegg.com', 'coursehero.com',
  'brainly.com', 'quizlet.com', 'bartleby.com',
]);

function classifyDomain(domain) {
  if (HIGH_RISK_DOMAINS.has(domain?.toLowerCase())) return 'high';
  return 'normal';
}

/* ─── Tab Configuration ──────────────────────────────────────────── */

const TABS = [
  { key: 'devices', label: 'Devices', icon: Usb },
  { key: 'network', label: 'Network', icon: Globe },
  { key: 'processes', label: 'Processes', icon: Terminal },
  { key: 'terminal', label: 'Terminal', icon: Code },
];

/* ─── Main Component ─────────────────────────────────────────────── */

export default function StudentDetails() {
  const { rollNo } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('sessionId');

  const [student, setStudent] = useState(null);
  const [devices, setDevices] = useState({ usb: [], external: [] });
  const [network, setNetwork] = useState(null);
  const [processes, setProcesses] = useState([]);
  const [domainActivity, setDomainActivity] = useState([]);
  const [terminalEvents, setTerminalEvents] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [highlightedPids, setHighlightedPids] = useState(new Set());
  const [activeTab, setActiveTab] = useState('processes');

  const wsRef = useRef(null);
  const teacherName = localStorage.getItem('teacherName') || 'Professor';
  const { liveSession } = useSession();

  useEffect(() => {
    loadStudentData();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [rollNo]);

  useEffect(() => {
    if (sessionId) {
      connectWebSocket();
    }
  }, [sessionId, rollNo]);

  const loadStudentData = async () => {
    try {
      const [studentData, devicesData, networkData] = await Promise.all([
        api.students.getById(rollNo),
        api.students.getDevices(rollNo),
        api.students.getNetwork(rollNo),
      ]);

      setStudent(studentData);
      setDevices(devicesData);
      setNetwork(networkData);
    } catch (error) {
      console.error('Error loading student data:', error);
    } finally {
      setLoading(false);
    }
  };

  const connectWebSocket = () => {
    const token = localStorage.getItem('token');
    if (!token || !sessionId) return;

    const ws = new WebSocketService();
    wsRef.current = ws;

    ws.on('connected', () => {
      setConnectionStatus('connected');
      setReconnectAttempt(0);
    });

    ws.on('disconnected', () => {
      setConnectionStatus('disconnected');
    });

    ws.on('reconnecting', ({ attempt, delay }) => {
      setConnectionStatus('reconnecting');
      setReconnectAttempt(attempt);
    });

    ws.on('connectionLost', () => {
      setConnectionStatus('lost');
    });

    /* ── Process events ─────────────────────────────────────── */

    ws.on('process_snapshot', (data) => {
      setProcesses(data);
    });

    ws.on('process_new', (data) => {
      setProcesses((prev) => [...prev, data]);
      flashHighlight(data.pid);
    });

    ws.on('process_update', (data) => {
      setProcesses((prev) =>
        prev.map((p) => (p.pid === data.pid ? { ...p, ...data } : p))
      );
    });

    ws.on('process_end', (data) => {
      setProcesses((prev) =>
        prev.map((p) =>
          p.pid === data.pid ? { ...p, status: 'ended' } : p
        )
      );
      setTimeout(() => {
        setProcesses((prev) => prev.filter((p) => p.pid !== data.pid));
      }, 5000);
    });

    /* ── Device events ──────────────────────────────────────── */

    ws.on('devices_snapshot', (data) => {
      setDevices(data);
    });

    ws.on('device_connected', (data) => {
      setDevices((prev) => {
        const key = data.type === 'usb' ? 'usb' : 'external';
        return {
          ...prev,
          [key]: [...(prev[key] || []), data],
        };
      });
    });

    ws.on('device_disconnected', (data) => {
      setDevices((prev) => ({
        usb: (prev.usb || []).filter((d) => d.id !== data.id),
        external: (prev.external || []).filter((d) => d.id !== data.id),
      }));
    });

    /* ── Domain activity events ─────────────────────────────── */

    ws.on('domain_activity', (data) => {
      if (Array.isArray(data)) {
        setDomainActivity((prev) => {
          const merged = new Map(prev.map((d) => [d.domain, d]));
          for (const entry of data) {
            const existing = merged.get(entry.domain);
            if (existing) {
              merged.set(entry.domain, {
                ...existing,
                request_count: (existing.request_count || 0) + (entry.count || entry.request_count || 0),
                risk_level: entry.risk_level || classifyDomain(entry.domain),
              });
            } else {
              merged.set(entry.domain, {
                domain: entry.domain,
                request_count: entry.count || entry.request_count || 0,
                risk_level: entry.risk_level || classifyDomain(entry.domain),
              });
            }
          }
          return Array.from(merged.values()).sort(
            (a, b) => (b.request_count || 0) - (a.request_count || 0)
          );
        });
      }
    });

    /* ── Terminal events ─────────────────────────────── */

    ws.on('terminal_events_snapshot', (data) => {
      setTerminalEvents(data || []);
    });

    ws.on('terminal_request', (data) => {
      setTerminalEvents((prev) => [data, ...prev].slice(0, 100));
    });

    ws.on('terminal_command', (data) => {
      setTerminalEvents((prev) => [data, ...prev].slice(0, 100));
    });

    ws.connect(sessionId, rollNo, token).catch((error) => {
      console.error('WebSocket connection error:', error);
      setConnectionStatus('error');
    });
  };

  const flashHighlight = (pid) => {
    setHighlightedPids((prev) => new Set(prev).add(pid));
    setTimeout(() => {
      setHighlightedPids((prev) => {
        const next = new Set(prev);
        next.delete(pid);
        return next;
      });
    }, 1500);
  };

  /* ── Derived data ─────────────────────────────────────────── */

  const highRiskProcesses = processes.filter(
    (p) => p.risk_level === 'high' && p.status !== 'ended'
  );
  const suspiciousProcesses = processes.filter(
    (p) => p.risk_level === 'medium' && p.status !== 'ended'
  );

  const allDevices = [...(devices.usb || []), ...(devices.external || [])];
  const riskyDevices = allDevices.filter((d) => d.risk_level === 'high' || d.risk_level === 'medium');
  const highRiskDomains = domainActivity.filter((d) => d.risk_level === 'high');
  const highRiskTerminal = terminalEvents.filter((d) => d.risk_level === 'high');

  const hasAnyActivity =
    highRiskProcesses.length > 0 ||
    suspiciousProcesses.length > 0 ||
    riskyDevices.length > 0 ||
    highRiskDomains.length > 0 ||
    highRiskTerminal.length > 0;

  /* ── Connection badge ─────────────────────────────────────── */

  const getConnectionStatusBadge = () => {
    switch (connectionStatus) {
      case 'connected':
        return (
          <div className="flex items-center space-x-2 text-[var(--color-success)]">
            <Wifi className="h-5 w-5" />
            <span className="font-medium">Connected</span>
          </div>
        );
      case 'connecting':
        return (
          <div className="flex items-center space-x-2 text-[var(--color-warning)]">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[var(--color-warning)]"></div>
            <span className="font-medium">Connecting...</span>
          </div>
        );
      case 'reconnecting':
        return (
          <div className="flex items-center space-x-2 text-[var(--color-warning)]">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[var(--color-warning)]"></div>
            <span className="font-medium">Reconnecting (Attempt {reconnectAttempt})</span>
          </div>
        );
      case 'lost':
      case 'disconnected':
      case 'error':
        return (
          <div className="flex items-center space-x-2 text-[var(--color-error)]">
            <WifiOff className="h-5 w-5" />
            <span className="font-medium">Connection Lost</span>
          </div>
        );
      default:
        return null;
    }
  };

  /* ── Loading state ────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--color-gray-50)] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-primary)] mx-auto"></div>
          <p className="mt-4 text-[var(--color-gray-600)]">Loading student details...</p>
        </div>
      </div>
    );
  }

  /* ── Section: Devices ─────────────────────────────────────── */

  const renderDevicesSection = () => (
    <div className="space-y-4">
      <SectionHeader icon={Usb} title="Connected Devices" count={allDevices.length} />
      {allDevices.length === 0 ? (
        <div className="text-center py-10">
          <Monitor className="h-10 w-10 mx-auto text-[var(--color-gray-300)] mb-3" />
          <p className="text-sm text-[var(--color-gray-500)]">No devices connected</p>
        </div>
      ) : (
        <div className="space-y-3">
          {allDevices.map((device, index) => (
            <div
              key={device.id || index}
              className={`flex items-center justify-between p-4 rounded-xl border transition-all duration-200 ${
                device.risk_level === 'high'
                  ? 'border-[var(--color-error)] bg-red-50'
                  : device.risk_level === 'medium'
                  ? 'border-[var(--color-warning)] bg-amber-50'
                  : 'border-[var(--color-gray-200)] bg-[var(--color-gray-50)]'
              }`}
            >
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm text-[var(--color-gray-900)]">
                  {device.readable_name || (device.device_type === 'usb' ? 'USB Device' : 'External Storage')}
                </p>
                {device.message && (
                  <p className="text-xs text-[var(--color-gray-500)] mt-0.5">{device.message}</p>
                )}
                {device.metadata && (
                  <div className="mt-1.5 flex flex-wrap gap-2">
                    {device.metadata.mountpoint && (
                      <span className="text-xs bg-[var(--color-gray-100)] text-[var(--color-gray-600)] px-2 py-0.5 rounded-full">
                        {device.metadata.mountpoint}
                      </span>
                    )}
                    {device.metadata.total_gb && (
                      <span className="text-xs bg-[var(--color-gray-100)] text-[var(--color-gray-600)] px-2 py-0.5 rounded-full">
                        {device.metadata.total_gb} GB
                      </span>
                    )}
                  </div>
                )}
              </div>
              <RiskBadge level={device.risk_level || 'medium'} />
            </div>
          ))}
        </div>
      )}
    </div>
  );

  /* ── Section: Network (Top Websites) ──────────────────────── */

  const renderNetworkSection = () => {
    const sortedDomains = [...domainActivity].sort(
      (a, b) => (b.request_count || 0) - (a.request_count || 0)
    );

    return (
      <div className="space-y-4">
        <SectionHeader icon={Globe} title="Top Websites Accessed" count={sortedDomains.length} />
        {sortedDomains.length === 0 ? (
          <div className="text-center py-10">
            <Globe className="h-10 w-10 mx-auto text-[var(--color-gray-300)] mb-3" />
            <p className="text-sm text-[var(--color-gray-500)]">No domain activity recorded</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sortedDomains.map((entry) => {
              const risk = entry.risk_level || classifyDomain(entry.domain);
              return (
                <div
                  key={entry.domain}
                  className={`flex items-center justify-between p-3 rounded-lg transition-all duration-200 ${
                    risk === 'high'
                      ? 'bg-red-50 border border-[var(--color-error)] border-opacity-30'
                      : 'bg-[var(--color-gray-50)] hover:bg-[var(--color-gray-100)]'
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[var(--color-gray-900)] truncate">
                      {entry.domain}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 ml-4 shrink-0">
                    <span className="text-xs text-[var(--color-gray-500)]">
                      {entry.request_count} request{entry.request_count !== 1 ? 's' : ''}
                    </span>
                    <RiskBadge level={risk} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  /* ── Section: Processes ───────────────────────────────────── */

  const renderProcessList = (procs, riskLevel, colorClasses) => (
    <div className="space-y-2">
      {procs.map((proc) => (
        <div
          key={proc.pid}
          className={`flex items-center justify-between p-3 rounded-lg transition-all duration-300 ${
            highlightedPids.has(proc.pid)
              ? `${colorClasses.highlightBg}`
              : `${colorClasses.hoverBg}`
          }`}
        >
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm text-[var(--color-gray-900)]">
              {proc.label || proc.name}
            </p>
            <p className="text-xs text-[var(--color-gray-500)] mt-0.5">
              PID: {proc.pid} · CPU: {Number(proc.cpu)?.toFixed(1)}% · Mem: {Number(proc.memory)?.toFixed(1)} MB
            </p>
          </div>
          <RiskBadge level={riskLevel} />
        </div>
      ))}
    </div>
  );

  const renderProcessesSection = () => {
    const noProcesses = highRiskProcesses.length === 0 && suspiciousProcesses.length === 0;

    return (
      <div className="space-y-6">
        {/* High Risk Processes */}
        {highRiskProcesses.length > 0 && (
          <div>
            <SectionHeader
              icon={ShieldAlert}
              title="High Risk Processes"
              count={highRiskProcesses.length}
              rightContent={
                <span className="text-xs font-semibold text-[var(--color-error)] bg-[var(--color-error)] bg-opacity-10 px-3 py-1 rounded-full animate-pulse">
                  ⚠ CRITICAL
                </span>
              }
            />
            {renderProcessList(highRiskProcesses, 'high', {
              highlightBg: 'bg-[var(--color-error)] bg-opacity-10',
              hoverBg: 'bg-red-50 hover:bg-red-100',
            })}
          </div>
        )}

        {/* Suspicious Processes */}
        {suspiciousProcesses.length > 0 && (
          <div>
            <SectionHeader
              icon={Shield}
              title="Suspicious Processes"
              count={suspiciousProcesses.length}
            />
            {renderProcessList(suspiciousProcesses, 'medium', {
              highlightBg: 'bg-[var(--color-warning)] bg-opacity-10',
              hoverBg: 'bg-amber-50 hover:bg-amber-100',
            })}
          </div>
        )}

        {/* Empty state */}
        {noProcesses && (
          <div className="text-center py-10">
            <Activity className="h-10 w-10 mx-auto text-[var(--color-gray-300)] mb-3" />
            <h3 className="text-lg font-semibold text-[var(--color-gray-700)] mb-1">
              {connectionStatus === 'connected' ? 'No Notable Processes' : 'Waiting for Connection...'}
            </h3>
            <p className="text-sm text-[var(--color-gray-500)]">
              {connectionStatus === 'connected'
                ? 'No high-risk or suspicious processes detected.'
                : 'Process data will appear once the student agent connects.'}
            </p>
          </div>
        )}
      </div>
    );
  };

  /* ── Section: Terminal Activity ──────────────────────────── */

  const renderTerminalSection = () => {
    return (
      <div className="space-y-4">
        <SectionHeader icon={Code} title="Terminal Activity" count={terminalEvents.length} />
        {terminalEvents.length === 0 ? (
          <div className="text-center py-10">
            <Code className="h-10 w-10 mx-auto text-[var(--color-gray-300)] mb-3" />
            <p className="text-sm text-[var(--color-gray-500)]">No terminal activity recorded</p>
          </div>
        ) : (
          <div className="space-y-3">
            {terminalEvents.map((event) => (
              <div
                key={event.id || `${event.detected_at}-${event.tool}`}
                className={`flex items-start justify-between p-4 rounded-xl border transition-all duration-200 ${
                  event.risk_level === 'high'
                    ? 'border-[var(--color-error)] bg-red-50'
                    : event.risk_level === 'medium'
                    ? 'border-[var(--color-warning)] bg-amber-50'
                    : 'border-[var(--color-success)] bg-emerald-50'
                }`}
              >
                <div className="flex-1 min-w-0 pr-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-sm text-[var(--color-gray-900)]">
                      {event.tool}
                    </span>
                    <span className="text-xs text-[var(--color-gray-500)]">
                      {new Date(event.detected_at).toLocaleTimeString()}
                    </span>
                    {event.pid && (
                      <span className="text-xs text-[var(--color-gray-500)] rounded bg-white px-1 border border-[var(--color-gray-200)]">
                        PID: {event.pid}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-mono text-[var(--color-gray-800)] break-all mt-2 bg-white bg-opacity-70 p-2 rounded border border-white border-opacity-40">
                    {event.event_type === 'terminal_command' ? event.full_command : `${event.remote_ip}${event.remote_port ? `:${event.remote_port}` : ''} ${event.remote_host ? `(${event.remote_host})` : ''}`}
                  </p>
                  {event.message && (
                    <p className="text-xs text-[var(--color-gray-600)] mt-2">
                      {event.message}
                    </p>
                  )}
                </div>
                <div className="shrink-0 flex flex-col items-end gap-2">
                  <RiskBadge level={event.risk_level || 'medium'} />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-500)]">
                    {event.event_type === 'terminal_command' ? 'Auditd' : 'SS'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  /* ── Render ───────────────────────────────────────────────── */

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      <Sidebar />
      <div className="ml-64">
        <Topbar teacherName={teacherName} />
        <main className={`p-8 ${liveSession ? 'mt-28' : 'mt-16'}`}>
          <div className="max-w-4xl mx-auto">
            {/* Header */}
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <Button
                  variant="ghost"
                  onClick={() => navigate(`/live-session/${sessionId}`)}
                >
                  <ArrowLeft className="h-5 w-5 mr-2" />
                  Back to Session
                </Button>
                <div>
                  <h1 className="text-3xl font-bold text-[var(--color-gray-900)]">
                    {rollNo}
                  </h1>
                  <p className="text-[var(--color-gray-600)]">{student?.name}</p>
                </div>
              </div>
              {getConnectionStatusBadge()}
            </div>

            {/* No suspicious activity banner */}
            {!hasAnyActivity && connectionStatus === 'connected' && (
              <div className="mb-6 p-4 bg-emerald-50 border border-[var(--color-success)] rounded-xl flex items-center gap-3">
                <ShieldCheck className="h-6 w-6 text-[var(--color-success)]" />
                <div>
                  <p className="font-semibold text-[var(--color-success)]">No Suspicious Activity Detected</p>
                  <p className="text-sm text-[var(--color-gray-600)]">This student has no flagged processes, devices, or domain access.</p>
                </div>
              </div>
            )}

            {/* Tab Bar */}
            <div className="mb-6 flex border-b border-[var(--color-gray-200)]">
              {TABS.map((tab) => {
                const isActive = activeTab === tab.key;
                const TabIcon = tab.icon;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors duration-200 -mb-px ${
                      isActive
                        ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                        : 'border-transparent text-[var(--color-gray-500)] hover:text-[var(--color-gray-700)] hover:border-[var(--color-gray-300)]'
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
              {activeTab === 'devices' && renderDevicesSection()}
              {activeTab === 'network' && renderNetworkSection()}
              {activeTab === 'processes' && renderProcessesSection()}
              {activeTab === 'terminal' && renderTerminalSection()}
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}
