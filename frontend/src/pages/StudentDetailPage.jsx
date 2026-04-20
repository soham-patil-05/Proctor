import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import StatusBadge from '../components/ui/StatusBadge';
import { getStudentDetail } from '../services/api';

const TABS = ['Processes', 'Devices', 'Network', 'Domain Activity', 'Terminal Events', 'Browser History'];
const PROCESS_RISK_ORDER = { dangerous: 0, suspicious: 1, safe: 2 };

function riskVariant(level) {
  const v = (level || '').toLowerCase();
  if (['dangerous', 'suspicious', 'safe', 'high', 'medium', 'low'].includes(v)) return v;
  return null;
}

function renderRisk(level) {
  const variant = riskVariant(level);
  if (!variant) return '—';
  return <StatusBadge variant={variant} />;
}

function toLocalDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

function truncateUrl(url) {
  if (!url) return '—';
  return url.length > 60 ? `${url.slice(0, 60)}...` : url;
}

function tableClass() {
  return 'w-full text-sm border-collapse';
}

function thClass() {
  return 'border-b border-[var(--color-gray-300)] text-left py-2 px-2 font-semibold';
}

function tdClass() {
  return 'border-b border-[var(--color-gray-200)] py-2 px-2 align-top';
}

export default function StudentDetailPage() {
  const navigate = useNavigate();
  const { rollNo } = useParams();
  const [search] = useSearchParams();
  const sessionId = search.get('sessionId') || '';

  const [activeTab, setActiveTab] = useState('Processes');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError('');
        const detail = await getStudentDetail(rollNo, sessionId);
        setData(detail);
      } catch (err) {
        setError(err.message || 'Failed to load details');
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [rollNo, sessionId]);

  const processes = useMemo(() => {
    const rows = [...(data?.processes || [])]
      .filter((p) => (p.status || '').toLowerCase() !== 'ended')
      .sort((a, b) => {
        const ra = PROCESS_RISK_ORDER[(a.riskLevel || '').toLowerCase()] ?? 3;
        const rb = PROCESS_RISK_ORDER[(b.riskLevel || '').toLowerCase()] ?? 3;
        if (ra !== rb) return ra - rb;
        return (Number(b.cpuPercent) || 0) - (Number(a.cpuPercent) || 0);
      });
    return rows;
  }, [data]);

  const usbDevices = useMemo(
    () => (data?.devices?.usb || []).filter((d) => (d.deviceType || '').toLowerCase() === 'usb'),
    [data]
  );

  const externalDevices = useMemo(
    () => (data?.devices?.external || []).filter((d) => (d.deviceType || '').toLowerCase() !== 'usb'),
    [data]
  );

  const domainActivity = useMemo(
    () => [...(data?.domainActivity || [])].sort((a, b) => (Number(b.requestCount) || 0) - (Number(a.requestCount) || 0)),
    [data]
  );

  const terminalEvents = useMemo(
    () => [...(data?.terminalEvents || [])]
      .sort((a, b) => new Date(b.detectedAt || 0).getTime() - new Date(a.detectedAt || 0).getTime())
      .slice(0, 200),
    [data]
  );

  const browserHistory = useMemo(
    () => [...(data?.browserHistory || [])]
      .sort((a, b) => new Date(b.lastVisit || 0).getTime() - new Date(a.lastVisit || 0).getTime()),
    [data]
  );

  if (loading) return <div className="min-h-screen p-6">Loading...</div>;
  if (error) return <div className="min-h-screen p-6 text-[var(--color-error)]">{error}</div>;

  const activeConnections = Array.isArray(data?.network?.activeConnections) ? data.network.activeConnections : [];

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

        <div className="mb-4 flex flex-wrap gap-2">
          {TABS.map((tab) => (
            <Button key={tab} variant={activeTab === tab ? 'primary' : 'outline'} size="sm" onClick={() => setActiveTab(tab)}>
              {tab}
            </Button>
          ))}
        </div>

        <Card className="p-6 overflow-x-auto">
          {activeTab === 'Processes' && (
            <table className={tableClass()}>
              <thead>
                <tr>
                  {['PID', 'Process Name', 'CPU %', 'Memory (MB)', 'Status', 'Risk Level', 'Category'].map((h) => (
                    <th key={h} className={thClass()}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {processes.map((p, idx) => (
                  <tr key={`${p.pid}-${idx}`}>
                    <td className={tdClass()}>{p.pid ?? '—'}</td>
                    <td className={tdClass()}>{p.processName || '—'}</td>
                    <td className={tdClass()}>{Number(p.cpuPercent || 0).toFixed(2)}</td>
                    <td className={tdClass()}>{Number(p.memoryMb || 0).toFixed(1)}</td>
                    <td className={tdClass()}>{['running', 'sleeping', 'stopped', 'zombie'].includes((p.status || '').toLowerCase()) ? (p.status || '').toLowerCase() : (p.status || '—')}</td>
                    <td className={tdClass()}>{renderRisk(p.riskLevel)}</td>
                    <td className={tdClass()}>{p.category || '—'}</td>
                  </tr>
                ))}
                {processes.length === 0 && <tr><td className={tdClass()} colSpan={7}>No process data.</td></tr>}
              </tbody>
            </table>
          )}

          {activeTab === 'Devices' && (
            <div className="space-y-8">
              <div>
                <h3 className="font-semibold mb-2">USB Devices</h3>
                <table className={tableClass()}>
                  <thead>
                    <tr>
                      {['Device Name', 'Readable Name', 'Type', 'Risk Level', 'Connected At', 'Status'].map((h) => (
                        <th key={h} className={thClass()}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {usbDevices.map((d, idx) => (
                      <tr key={`usb-${d.deviceId}-${idx}`}>
                        <td className={tdClass()}>{d.deviceName || '—'}</td>
                        <td className={tdClass()}>{d.readableName || '—'}</td>
                        <td className={tdClass()}>{d.deviceType || '—'}</td>
                        <td className={tdClass()}>{renderRisk(d.riskLevel)}</td>
                        <td className={tdClass()}>{toLocalDate(d.connectedAt)}</td>
                        <td className={tdClass()}>{d.disconnectedAt ? 'Disconnected' : 'Connected'}</td>
                      </tr>
                    ))}
                    {usbDevices.length === 0 && <tr><td className={tdClass()} colSpan={6}>No USB devices.</td></tr>}
                  </tbody>
                </table>
              </div>

              <div>
                <h3 className="font-semibold mb-2">External Drives</h3>
                <table className={tableClass()}>
                  <thead>
                    <tr>
                      {['Device Name', 'Readable Name', 'Type', 'Risk Level', 'Connected At', 'Status'].map((h) => (
                        <th key={h} className={thClass()}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {externalDevices.map((d, idx) => (
                      <tr key={`ext-${d.deviceId}-${idx}`}>
                        <td className={tdClass()}>{d.deviceName || '—'}</td>
                        <td className={tdClass()}>{d.readableName || '—'}</td>
                        <td className={tdClass()}>{d.deviceType || '—'}</td>
                        <td className={tdClass()}>{renderRisk(d.riskLevel)}</td>
                        <td className={tdClass()}>{toLocalDate(d.connectedAt)}</td>
                        <td className={tdClass()}>{d.disconnectedAt ? 'Disconnected' : 'Connected'}</td>
                      </tr>
                    ))}
                    {externalDevices.length === 0 && <tr><td className={tdClass()} colSpan={6}>No external drives.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'Network' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-[var(--color-gray-100)] p-3 rounded">
                <div><span className="font-semibold">IP Address:</span> {data?.network?.ipAddress || '—'}</div>
                <div><span className="font-semibold">Gateway:</span> {data?.network?.gateway || '—'}</div>
                <div><span className="font-semibold">DNS:</span> {Array.isArray(data?.network?.dns) ? data.network.dns.join(', ') || '—' : '—'}</div>
              </div>
              <div>
                <div className="font-semibold mb-2">Active Connections</div>
                {activeConnections.length === 0 ? (
                  <p>No active connections.</p>
                ) : (
                  <table className={tableClass()}>
                    <thead>
                      <tr>
                        {['Remote IP', 'Remote Host', 'Remote Port', 'PID', 'Process'].map((h) => (
                          <th key={h} className={thClass()}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {activeConnections.map((c, idx) => (
                        <tr key={`conn-${idx}`}>
                          <td className={tdClass()}>{c.remoteIp || '—'}</td>
                          <td className={tdClass()}>{c.remoteHost || '—'}</td>
                          <td className={tdClass()}>{c.remotePort || '—'}</td>
                          <td className={tdClass()}>{c.pid || '—'}</td>
                          <td className={tdClass()}>{c.process || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {activeTab === 'Domain Activity' && (
            <table className={tableClass()}>
              <thead>
                <tr>
                  {['Domain', 'Request Count', 'Risk Level', 'Last Accessed'].map((h) => (
                    <th key={h} className={thClass()}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {domainActivity.map((d, idx) => (
                  <tr key={`${d.domain}-${idx}`}>
                    <td className={tdClass()}>{d.domain || '—'}</td>
                    <td className={tdClass()}>{d.requestCount ?? 0}</td>
                    <td className={tdClass()}>{renderRisk(d.riskLevel)}</td>
                    <td className={tdClass()}>{toLocalDate(d.lastAccessed)}</td>
                  </tr>
                ))}
                {domainActivity.length === 0 && <tr><td className={tdClass()} colSpan={4}>No domain activity.</td></tr>}
              </tbody>
            </table>
          )}

          {activeTab === 'Terminal Events' && (
            <table className={tableClass()}>
              <thead>
                <tr>
                  {['Time', 'Event Type', 'Tool', 'Remote IP', 'Remote Host', 'Port', 'PID', 'Command', 'Risk Level', 'Message'].map((h) => (
                    <th key={h} className={thClass()}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {terminalEvents.map((e, idx) => (
                  <tr key={`${e.eventType}-${idx}`}>
                    <td className={tdClass()}>{toLocalDate(e.detectedAt)}</td>
                    <td className={tdClass()}>{e.eventType || '—'}</td>
                    <td className={tdClass()}>{e.tool || '—'}</td>
                    <td className={tdClass()}>{e.remoteIp || '—'}</td>
                    <td className={tdClass()}>{e.remoteHost || '—'}</td>
                    <td className={tdClass()}>{e.remotePort || '—'}</td>
                    <td className={tdClass()}>{e.pid || '—'}</td>
                    <td className={tdClass()}>{e.fullCommand || '—'}</td>
                    <td className={tdClass()}>{renderRisk(e.riskLevel)}</td>
                    <td className={tdClass()}>{e.message || '—'}</td>
                  </tr>
                ))}
                {terminalEvents.length === 0 && <tr><td className={tdClass()} colSpan={10}>No terminal events.</td></tr>}
              </tbody>
            </table>
          )}

          {activeTab === 'Browser History' && (
            <table className={tableClass()}>
              <thead>
                <tr>
                  {['URL', 'Title', 'Visit Count', 'Last Visit'].map((h) => (
                    <th key={h} className={thClass()}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {browserHistory.map((h, idx) => (
                  <tr key={`${h.url}-${idx}`}>
                    <td className={tdClass()} title={h.url || ''}>{truncateUrl(h.url)}</td>
                    <td className={tdClass()}>{h.title || '—'}</td>
                    <td className={tdClass()}>{h.visitCount ?? 0}</td>
                    <td className={tdClass()}>{toLocalDate(h.lastVisit)}</td>
                  </tr>
                ))}
                {browserHistory.length === 0 && <tr><td className={tdClass()} colSpan={4}>No browser history.</td></tr>}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
