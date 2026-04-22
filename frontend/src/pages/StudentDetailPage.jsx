import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Code, History, Terminal, Usb, ArrowLeft, ChevronLeft } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import { getStudentDetail } from '../services/api';

// ─── Constants ───────────────────────────────────────────────────────────────

const TABS = [
  { key: 'devices', label: 'USB Devices', icon: Usb },
  { key: 'network', label: 'Browser History', icon: History },
  { key: 'processes', label: 'Processes', icon: Terminal },
  { key: 'terminal', label: 'Terminal', icon: Code },
];

const RISK_CONFIG = {
  high: { label: 'High Risk', dot: '#DC2626', bg: '#FEF2F2', text: '#DC2626', border: '#FECACA' },
  medium: { label: 'Warning', dot: '#D97706', bg: '#FFFBEB', text: '#D97706', border: '#FDE68A' },
  low: { label: 'Safe', dot: '#059669', bg: '#ECFDF5', text: '#059669', border: '#A7F3D0' },
  normal: { label: 'Normal', dot: '#059669', bg: '#ECFDF5', text: '#059669', border: '#A7F3D0' },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function riskCfg(level) {
  return RISK_CONFIG[String(level || 'normal').toLowerCase()] || RISK_CONFIG.normal;
}

function RiskBadge({ riskLevel }) {
  const cfg = riskCfg(riskLevel);
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap"
      style={{ backgroundColor: cfg.bg, color: cfg.text }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: cfg.dot }} />
      {cfg.label}
    </span>
  );
}

function hostnameFallback(url) {
  if (!url) return '—';
  try { return new URL(url).hostname || url; } catch { return url; }
}

function titleFallback(entry) {
  if (entry?.title) return entry.title;
  if (!entry?.url) return '—';
  try {
    const p = new URL(entry.url);
    return `${p.hostname}${p.pathname || ''}` || entry.url;
  } catch { return entry.url; }
}

function formatUnixTime(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return '—';
  return new Date(n * 1000).toLocaleString();
}

function formatIsoTime(value) {
  if (!value) return '—';
  const d = new Date(value);
  return isNaN(d.getTime()) ? '—' : d.toLocaleString();
}

function terminalContent(event) {
  if ((event?.eventType || '').toLowerCase() === 'terminal_command') {
    return event?.fullCommand || '—';
  }
  const bits = [];
  if (event?.remoteIp && event?.remotePort) bits.push(`${event.remoteIp}:${event.remotePort}`);
  else if (event?.remoteIp) bits.push(event.remoteIp);
  if (event?.remoteHost) bits.push(`(${event.remoteHost})`);
  return bits.join(' ') || '—';
}

function groupProcesses(processRows) {
  const grouped = new Map();
  for (const row of processRows) {
    const groupName = (row.label || row.name || 'Unknown Process').trim();
    const existing = grouped.get(groupName) || {
      name: groupName, pids: [], count: 0, totalCpu: 0, totalMemory: 0,
      riskLevel: row.riskLevel || 'normal',
    };
    if (row.pid !== null && row.pid !== undefined) existing.pids.push(row.pid);
    existing.count += 1;
    existing.totalCpu += Number(row.cpu || 0);
    existing.totalMemory += Number(row.memory || 0);
    existing.riskLevel = row.riskLevel || existing.riskLevel;
    grouped.set(groupName, existing);
  }
  return Array.from(grouped.values());
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function DetailSkeleton() {
  return (
    <div className="space-y-3 p-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="skeleton h-20 rounded-lg" />
      ))}
    </div>
  );
}

// ─── Tab content sections ─────────────────────────────────────────────────────

function DevicesTab({ devices }) {
  if (devices.length === 0) return <EmptyState icon={Usb} title="No USB devices" message="No USB devices were connected during this session." />;
  return (
    <div className="space-y-2.5">
      {devices.map((device, idx) => {
        const cfg = riskCfg(device.riskLevel);
        return (
          <div
            key={`${device.id || 'dev'}-${idx}`}
            className="rounded-lg p-4 border"
            style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-[var(--color-gray-900)]">
                  {device.readableName || 'USB Storage Device'}
                </div>
                {device.message && (
                  <div className="text-xs text-[var(--color-gray-600)] mt-1">{device.message}</div>
                )}
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {device.metadata?.mountpoint && (
                    <span className="px-2 py-0.5 rounded text-xs bg-white border border-[var(--color-gray-200)] text-[var(--color-gray-600)] font-mono">
                      {device.metadata.mountpoint}
                    </span>
                  )}
                  {device.metadata?.totalGb !== null && device.metadata?.totalGb !== undefined && (
                    <span className="px-2 py-0.5 rounded text-xs bg-white border border-[var(--color-gray-200)] text-[var(--color-gray-600)]">
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
  );
}

function NetworkTab({ browserHistory }) {
  if (browserHistory.length === 0) return <EmptyState icon={History} title="No browsing activity" message="No browser history was recorded during this session." />;
  return (
    <div className="space-y-2 max-h-[540px] overflow-y-auto pr-1">
      {browserHistory.map((entry, idx) => (
        <div
          key={`${entry.url || 'url'}-${idx}`}
          className="rounded-lg p-3.5 border border-[var(--color-gray-200)] bg-white hover:border-[var(--color-gray-300)] transition-colors duration-100"
        >
          <div className="font-medium text-sm text-[var(--color-gray-900)] truncate">{titleFallback(entry)}</div>
          <a
            href={entry.url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[var(--color-accent)] truncate block hover:underline"
            title={entry.url || ''}
          >
            {entry.url || '—'}
          </a>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-[var(--color-gray-400)]">
            {entry.browser && <span className="font-medium text-[var(--color-gray-500)]">{entry.browser}</span>}
            <span>{formatUnixTime(entry.lastVisited)}</span>
            {Number(entry.visitCount || 1) > 1 && (
              <span className="px-1.5 py-0.5 rounded bg-[var(--color-gray-100)] text-[var(--color-gray-500)]">
                {entry.visitCount} visits
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ProcessGroup({ groups, title, emptyText }) {
  if (groups.length === 0) {
    return (
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)] mb-2">{title}</h3>
        <p className="text-sm text-[var(--color-gray-400)] italic">{emptyText}</p>
      </div>
    );
  }
  return (
    <div>
      <div className="flex items-center gap-2 mb-2.5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-500)]">{title}</h3>
        <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-[var(--color-error-bg)] text-[var(--color-error)]">
          {groups.length}
        </span>
      </div>
      <div className="space-y-2">
        {groups.map((group) => {
          const cfg = riskCfg(group.riskLevel);
          return (
            <div
              key={`${group.riskLevel}-${group.name}`}
              className="rounded-lg p-3.5 border flex items-start justify-between gap-3"
              style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
            >
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-[var(--color-gray-900)]">
                  {group.name}
                  {group.count > 1 && (
                    <span className="ml-1.5 text-xs font-normal text-[var(--color-gray-500)]">
                      × {group.count} instances
                    </span>
                  )}
                </div>
                <div className="text-xs text-[var(--color-gray-500)] mt-1 font-mono">
                  PIDs: {group.pids.join(', ') || '—'} &nbsp;·&nbsp; CPU: {group.totalCpu.toFixed(1)}% &nbsp;·&nbsp; Mem: {group.totalMemory.toFixed(1)} MB
                </div>
              </div>
              <RiskBadge riskLevel={group.riskLevel} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProcessesTab({ groupedProcesses }) {
  const high = groupedProcesses.filter((p) => String(p.riskLevel || '').toLowerCase() === 'high');
  const medium = groupedProcesses.filter((p) => String(p.riskLevel || '').toLowerCase() === 'medium');
  if (high.length === 0 && medium.length === 0) {
    return <EmptyState icon={Terminal} title="No notable processes" message="No suspicious or high-risk processes were detected." />;
  }
  return (
    <div className="space-y-6">
      <ProcessGroup groups={high} title="High Risk" emptyText="No high-risk processes." />
      <ProcessGroup groups={medium} title="Suspicious" emptyText="No suspicious processes." />
    </div>
  );
}

function TerminalTab({ terminalEvents }) {
  if (terminalEvents.length === 0) return <EmptyState icon={Code} title="No terminal activity" message="No terminal commands or connections were recorded." />;
  return (
    <div className="space-y-2.5 max-h-[540px] overflow-y-auto pr-1">
      {terminalEvents.map((event, idx) => {
        const cfg = riskCfg(event.riskLevel);
        return (
          <div
            key={`${event.id || event.detectedAt || idx}`}
            className="rounded-lg p-4 border"
            style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <span className="font-semibold text-sm text-[var(--color-gray-900)]">{event.tool || 'unknown'}</span>
                  <span className="text-xs text-[var(--color-gray-400)]">{formatIsoTime(event.detectedAt)}</span>
                  {event.pid !== null && event.pid !== undefined && (
                    <span className="px-1.5 py-0.5 rounded text-xs bg-white border border-[var(--color-gray-200)] font-mono text-[var(--color-gray-500)]">
                      PID {event.pid}
                    </span>
                  )}
                  <span className="px-1.5 py-0.5 rounded text-xs bg-white border border-[var(--color-gray-200)] text-[var(--color-gray-500)]">
                    {(event.eventType || '').toLowerCase() === 'terminal_command' ? 'auditd' : 'ss'}
                  </span>
                </div>
                <pre className="p-2.5 rounded-lg bg-[var(--color-gray-900)] text-[var(--color-gray-100)] text-xs overflow-x-auto font-mono leading-relaxed">
                  {terminalContent(event)}
                </pre>
                {event.message && (
                  <div className="text-xs text-[var(--color-gray-500)] mt-2">{event.message}</div>
                )}
              </div>
              <RiskBadge riskLevel={event.riskLevel} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EmptyState({ icon: Icon, title, message }) {
  return (
    <div className="py-12 text-center">
      <div className="mx-auto h-11 w-11 rounded-full bg-[var(--color-gray-100)] flex items-center justify-center mb-3">
        <Icon size={20} className="text-[var(--color-gray-400)]" />
      </div>
      <p className="text-sm font-medium text-[var(--color-gray-600)]">{title}</p>
      <p className="text-xs text-[var(--color-gray-400)] mt-1">{message}</p>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function StudentDetailPage() {
  const navigate = useNavigate();
  const { rollNo } = useParams();
  const [search] = useSearchParams();
  const sessionId = search.get('sessionId') || '';

  const [activeTab, setActiveTab] = useState('devices');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState({
    devices: [], browserHistory: [], processes: [], terminalEvents: [],
  });

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        setLoading(true);
        setError('');
        const detail = await getStudentDetail(rollNo, sessionId);
        if (cancelled) return;
        setData({
          devices: Array.isArray(detail?.devices) ? detail.devices : [],
          browserHistory: Array.isArray(detail?.browserHistory) ? detail.browserHistory : [],
          processes: Array.isArray(detail?.processes) ? detail.processes : [],
          terminalEvents: Array.isArray(detail?.terminalEvents) ? detail.terminalEvents : [],
        });
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load details');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [rollNo, sessionId]);

  const browserHistory = useMemo(
    () => [...data.browserHistory].sort((a, b) => Number(b.lastVisited || 0) - Number(a.lastVisited || 0)),
    [data.browserHistory]
  );
  const terminalEvents = useMemo(
    () => [...data.terminalEvents].sort((a, b) => new Date(b.detectedAt || 0) - new Date(a.detectedAt || 0)),
    [data.terminalEvents]
  );
  const groupedProcesses = useMemo(() => groupProcesses(data.processes || []), [data.processes]);

  // Tab counts
  const counts = {
    devices: data.devices.length,
    network: data.browserHistory.length,
    processes: groupedProcesses.filter((p) => ['high', 'medium'].includes(String(p.riskLevel || '').toLowerCase())).length,
    terminal: data.terminalEvents.length,
  };

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      {/* Header */}
      <header className="bg-[var(--color-primary)] shadow-md">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="h-8 w-8 rounded-lg bg-white/10 hover:bg-white/20 transition-colors duration-150 flex items-center justify-center text-white shrink-0"
            title="Go back"
          >
            <ChevronLeft size={18} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-3">
              <h1 className="text-white font-bold text-lg truncate">{decodeURIComponent(rollNo)}</h1>
              <span className="text-white/40 text-sm hidden sm:inline">Session: {sessionId}</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-7">
        {error && (
          <div className="mb-5 px-4 py-3 bg-[var(--color-error-bg)] border border-[var(--color-error)] border-opacity-30 rounded-xl flex items-center gap-3 text-sm text-[var(--color-error)]">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" className="shrink-0">
              <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 4zm0 8a1 1 0 110-2 1 1 0 010 2z"/>
            </svg>
            {error}
          </div>
        )}

        <Card className="overflow-hidden">
          {/* Tabs */}
          <div className="border-b border-[var(--color-gray-200)] overflow-x-auto">
            <div className="flex px-2 min-w-max">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.key;
                const count = counts[tab.key];
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={`inline-flex items-center gap-2 px-4 py-3.5 text-sm font-medium border-b-2 whitespace-nowrap transition-all duration-150
                      ${isActive
                        ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
                        : 'border-transparent text-[var(--color-gray-500)] hover:text-[var(--color-gray-700)] hover:border-[var(--color-gray-200)]'
                      }`}
                  >
                    <Icon size={15} />
                    {tab.label}
                    {!loading && count > 0 && (
                      <span className={`px-1.5 py-0.5 rounded text-xs font-semibold
                        ${isActive ? 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]' : 'bg-[var(--color-gray-100)] text-[var(--color-gray-500)]'}`}>
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tab body */}
          {loading ? (
            <DetailSkeleton />
          ) : (
            <div className="p-6 fade-in">
              {activeTab === 'devices' && <DevicesTab devices={data.devices} />}
              {activeTab === 'network' && <NetworkTab browserHistory={browserHistory} />}
              {activeTab === 'processes' && <ProcessesTab groupedProcesses={groupedProcesses} />}
              {activeTab === 'terminal' && <TerminalTab terminalEvents={terminalEvents} />}
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
