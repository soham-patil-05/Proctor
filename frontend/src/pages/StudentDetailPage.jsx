import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Code, History, Terminal, Usb } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import { getStudentDetail } from '../services/api';

const TABS = [
  { key: 'devices', label: 'Devices', icon: Usb },
  { key: 'network', label: 'Network', icon: History },
  { key: 'processes', label: 'Processes', icon: Terminal },
  { key: 'terminal', label: 'Terminal', icon: Code },
];

const RISK_CONFIG = {
  high: { label: 'High Risk', dotColor: '#DC2626', bgTint: '#FEF2F2', textColor: '#DC2626' },
  medium: { label: 'Warning', dotColor: '#D97706', bgTint: '#FFFBEB', textColor: '#D97706' },
  low: { label: 'Safe', dotColor: '#059669', bgTint: '#ECFDF5', textColor: '#059669' },
  normal: { label: 'Normal', dotColor: '#059669', bgTint: '#ECFDF5', textColor: '#059669' },
};

function RiskBadge({ riskLevel }) {
  const level = String(riskLevel || 'normal').toLowerCase();
  const cfg = RISK_CONFIG[level] || RISK_CONFIG.normal;

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={{ backgroundColor: cfg.bgTint, color: cfg.textColor }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: cfg.dotColor }} />
      {cfg.label}
    </span>
  );
}

function hostnameFallback(url) {
  if (!url) return '—';
  try {
    const parsed = new URL(url);
    return parsed.hostname || url;
  } catch {
    return url;
  }
}

function titleFallback(entry) {
  if (entry?.title) return entry.title;
  if (!entry?.url) return '—';
  try {
    const parsed = new URL(entry.url);
    return `${parsed.hostname}${parsed.pathname || ''}` || entry.url;
  } catch {
    return entry.url;
  }
}

function formatUnixTime(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return '—';
  return new Date(n * 1000).toLocaleTimeString();
}

function formatIsoTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString();
}

function terminalContent(event) {
  if ((event?.eventType || '').toLowerCase() === 'terminal_command') {
    return event?.fullCommand || '—';
  }

  const bits = [];
  if (event?.remoteIp && event?.remotePort) {
    bits.push(`${event.remoteIp}:${event.remotePort}`);
  } else if (event?.remoteIp) {
    bits.push(event.remoteIp);
  }
  if (event?.remoteHost) {
    bits.push(`(${event.remoteHost})`);
  }
  return bits.join(' ') || '—';
}

function groupProcesses(processRows) {
  const grouped = new Map();

  for (const row of processRows) {
    const groupName = (row.label || row.name || 'Unknown Process').trim();
    const existing = grouped.get(groupName) || {
      name: groupName,
      pids: [],
      count: 0,
      totalCpu: 0,
      totalMemory: 0,
      riskLevel: row.riskLevel || 'normal',
    };

    if (row.pid !== null && row.pid !== undefined) {
      existing.pids.push(row.pid);
    }
    existing.count += 1;
    existing.totalCpu += Number(row.cpu || 0);
    existing.totalMemory += Number(row.memory || 0);
    existing.riskLevel = row.riskLevel || existing.riskLevel;

    grouped.set(groupName, existing);
  }

  return Array.from(grouped.values());
}

export default function StudentDetailPage() {
  const navigate = useNavigate();
  const { rollNo } = useParams();
  const [search] = useSearchParams();
  const sessionId = search.get('sessionId') || '';

  const [activeTab, setActiveTab] = useState('devices');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState({ devices: [], browserHistory: [], processes: [], terminalEvents: [] });

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError('');
        const detail = await getStudentDetail(rollNo, sessionId);
        setData({
          devices: Array.isArray(detail?.devices) ? detail.devices : [],
          browserHistory: Array.isArray(detail?.browserHistory) ? detail.browserHistory : [],
          processes: Array.isArray(detail?.processes) ? detail.processes : [],
          terminalEvents: Array.isArray(detail?.terminalEvents) ? detail.terminalEvents : [],
        });
      } catch (err) {
        setError(err.message || 'Failed to load details');
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [rollNo, sessionId]);

  const browserHistory = useMemo(
    () => [...data.browserHistory].sort((a, b) => Number(b.lastVisited || 0) - Number(a.lastVisited || 0)),
    [data.browserHistory]
  );

  const terminalEvents = useMemo(
    () => [...data.terminalEvents].sort((a, b) => new Date(b.detectedAt || 0).getTime() - new Date(a.detectedAt || 0).getTime()),
    [data.terminalEvents]
  );

  const groupedProcesses = useMemo(() => groupProcesses(data.processes || []), [data.processes]);
  const highRiskGroups = groupedProcesses.filter((p) => String(p.riskLevel || '').toLowerCase() === 'high');
  const mediumRiskGroups = groupedProcesses.filter((p) => String(p.riskLevel || '').toLowerCase() === 'medium');

  if (loading) return <div className="min-h-screen p-6">Loading...</div>;
  if (error) return <div className="min-h-screen p-6 text-[var(--color-error)]">{error}</div>;

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)] p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-[var(--color-gray-900)]">{rollNo}</h1>
            <p className="text-[var(--color-gray-600)]">Session: {sessionId}</p>
          </div>
          <Button variant="secondary" onClick={() => navigate('/')}>Back</Button>
        </div>

        <div className="mb-4 border-b border-[var(--color-gray-300)] flex flex-wrap gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 ${
                  isActive
                    ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                    : 'border-transparent text-[var(--color-gray-600)] hover:text-[var(--color-gray-900)]'
                }`}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        <Card className="p-6">
          {activeTab === 'devices' && (
            <div className="space-y-3">
              {data.devices.length === 0 && <p className="text-sm text-[var(--color-gray-600)]">No USB devices connected.</p>}
              {data.devices.map((device, idx) => {
                const risk = String(device.riskLevel || 'normal').toLowerCase();
                const cardTone =
                  risk === 'high'
                    ? { borderColor: '#F87171', backgroundColor: '#FEF2F2' }
                    : risk === 'medium'
                    ? { borderColor: '#FBBF24', backgroundColor: '#FFFBEB' }
                    : { borderColor: '#D1D5DB', backgroundColor: '#F9FAFB' };

                return (
                  <div key={`${device.id || 'dev'}-${idx}`} className="border rounded-lg p-3" style={cardTone}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold text-[var(--color-gray-900)]">{device.readableName || 'USB Storage Device'}</div>
                        {device.message && <div className="text-xs text-[var(--color-gray-700)] mt-1">{device.message}</div>}
                        <div className="flex flex-wrap gap-2 mt-2">
                          {device.metadata?.mountpoint && (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-white border border-[var(--color-gray-300)]">
                              {device.metadata.mountpoint}
                            </span>
                          )}
                          {device.metadata?.totalGb !== null && device.metadata?.totalGb !== undefined && (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-white border border-[var(--color-gray-300)]">
                              {device.metadata.totalGb} GB
                            </span>
                          )}
                        </div>
                      </div>
                      <RiskBadge riskLevel={device.riskLevel} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {activeTab === 'network' && (
            <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
              {browserHistory.length === 0 && (
                <p className="text-sm text-[var(--color-gray-600)]">No browsing activity since session started.</p>
              )}
              {browserHistory.map((entry, idx) => (
                <div key={`${entry.url || 'url'}-${idx}`} className="border border-[var(--color-gray-200)] rounded-lg p-3 bg-white">
                  <div className="font-semibold text-[var(--color-gray-900)]">{titleFallback(entry)}</div>
                  <div className="text-xs text-blue-700 truncate" title={entry.url || ''}>{entry.url || '—'}</div>
                  <div className="mt-2 text-xs text-[var(--color-gray-700)] flex flex-wrap gap-3">
                    <span>{entry.browser || '—'}</span>
                    <span>{formatUnixTime(entry.lastVisited)}</span>
                    {Number(entry.visitCount || 1) > 1 && <span>Visits: {entry.visitCount}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'processes' && (
            <div className="space-y-5">
              {highRiskGroups.length === 0 && mediumRiskGroups.length === 0 && (
                <p className="text-sm text-[var(--color-gray-600)]">No notable processes detected.</p>
              )}

              <div>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold">High Risk Processes</h3>
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-[#FEF2F2] text-[#991B1B] animate-pulse">⚠ CRITICAL</span>
                </div>
                <div className="space-y-2">
                  {highRiskGroups.map((group) => (
                    <div key={`high-${group.name}`} className="border border-[#F87171] rounded-lg p-3 bg-[#FEF2F2] flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold text-[var(--color-gray-900)]">
                          {group.name}
                          {group.count > 1 ? ` (${group.count} instances)` : ''}
                        </div>
                        <div className="text-xs text-[var(--color-gray-700)] mt-1">
                          PIDs: {group.pids.join(', ') || '—'} · CPU: {group.totalCpu.toFixed(1)}% · Mem: {group.totalMemory.toFixed(1)} MB
                        </div>
                      </div>
                      <RiskBadge riskLevel={group.riskLevel} />
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="font-semibold mb-2">Suspicious Processes</h3>
                <div className="space-y-2">
                  {mediumRiskGroups.map((group) => (
                    <div key={`medium-${group.name}`} className="border border-[#FBBF24] rounded-lg p-3 bg-[#FFFBEB] flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold text-[var(--color-gray-900)]">
                          {group.name}
                          {group.count > 1 ? ` (${group.count} instances)` : ''}
                        </div>
                        <div className="text-xs text-[var(--color-gray-700)] mt-1">
                          PIDs: {group.pids.join(', ') || '—'} · CPU: {group.totalCpu.toFixed(1)}% · Mem: {group.totalMemory.toFixed(1)} MB
                        </div>
                      </div>
                      <RiskBadge riskLevel={group.riskLevel} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'terminal' && (
            <div className="space-y-3">
              {terminalEvents.length === 0 && <p className="text-sm text-[var(--color-gray-600)]">No terminal activity recorded.</p>}
              {terminalEvents.map((event, idx) => {
                const risk = String(event.riskLevel || 'normal').toLowerCase();
                const cardTone =
                  risk === 'high'
                    ? { borderColor: '#F87171', backgroundColor: '#FEF2F2' }
                    : risk === 'medium'
                    ? { borderColor: '#FBBF24', backgroundColor: '#FFFBEB' }
                    : { borderColor: '#34D399', backgroundColor: '#ECFDF5' };

                return (
                  <div key={`${event.id || event.detectedAt || idx}`} className="border rounded-lg p-3" style={cardTone}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-[var(--color-gray-900)]">{event.tool || 'unknown'}</span>
                          <span className="text-xs text-[var(--color-gray-700)]">{formatIsoTime(event.detectedAt)}</span>
                          {event.pid !== null && event.pid !== undefined && (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-white border border-[var(--color-gray-300)]">PID: {event.pid}</span>
                          )}
                        </div>

                        <pre className="mt-2 p-2 rounded-md bg-[var(--color-gray-900)] text-[var(--color-gray-50)] text-xs overflow-x-auto font-mono">
                          {terminalContent(event)}
                        </pre>

                        {event.message && <div className="text-xs text-[var(--color-gray-700)] mt-2">{event.message}</div>}
                      </div>

                      <div className="flex flex-col items-end gap-2">
                        <RiskBadge riskLevel={event.riskLevel} />
                        <span className="text-xs text-[var(--color-gray-700)]">
                          {(event.eventType || '').toLowerCase() === 'terminal_command' ? 'Auditd' : 'SS'}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
