import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import StatusBadge from '../components/ui/StatusBadge';
import { getStudentDetail } from '../services/api';

const TABS = ['Processes', 'Devices', 'Network', 'Domain Activity', 'Terminal Events', 'Browser History'];

function normalizeStatus(level) {
  if (!level) return 'normal';
  if (level === 'high') return 'error';
  if (level === 'medium') return 'warning';
  return 'normal';
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

  if (loading) {
    return <div className="min-h-screen p-6">Loading...</div>;
  }

  if (error) {
    return <div className="min-h-screen p-6 text-[var(--color-error)]">{error}</div>;
  }

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)] p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-[var(--color-gray-900)]">{rollNo}</h1>
            <p className="text-[var(--color-gray-600)]">Session: {sessionId}</p>
          </div>
          <Button variant="secondary" onClick={() => navigate('/')}>Back</Button>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {TABS.map((tab) => (
            <Button
              key={tab}
              variant={activeTab === tab ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </Button>
          ))}
        </div>

        <Card className="p-6">
          {activeTab === 'Processes' && (
            <div className="space-y-3">
              {(data?.processes || []).map((p) => (
                <div key={`${p.pid}-${p.processName}`} className="border rounded-lg p-3 flex items-center justify-between">
                  <div>
                    <div className="font-semibold">{p.processName} (PID {p.pid})</div>
                    <div className="text-sm text-[var(--color-gray-600)]">CPU: {p.cpuPercent} | Memory: {p.memoryMb} MB | Status: {p.status} | Category: {p.category || '-'}</div>
                  </div>
                  <StatusBadge status={normalizeStatus(p.riskLevel)} />
                </div>
              ))}
              {(data?.processes || []).length === 0 && <p>No process data.</p>}
            </div>
          )}

          {activeTab === 'Devices' && (
            <div className="space-y-6">
              <div>
                <h2 className="font-semibold mb-2">USB</h2>
                {(data?.devices?.usb || []).map((d, idx) => (
                  <div key={`usb-${idx}`} className="border rounded-lg p-3 mb-2">
                    <div className="font-semibold">{d.readableName || d.deviceName || d.deviceId}</div>
                    <div className="text-sm text-[var(--color-gray-600)]">{d.deviceId}</div>
                    <StatusBadge status={normalizeStatus(d.riskLevel)} className="mt-2" />
                  </div>
                ))}
                {(data?.devices?.usb || []).length === 0 && <p>No USB devices.</p>}
              </div>
              <div>
                <h2 className="font-semibold mb-2">External</h2>
                {(data?.devices?.external || []).map((d, idx) => (
                  <div key={`ext-${idx}`} className="border rounded-lg p-3 mb-2">
                    <div className="font-semibold">{d.readableName || d.deviceName || d.deviceId}</div>
                    <div className="text-sm text-[var(--color-gray-600)]">{d.deviceId}</div>
                    <StatusBadge status={normalizeStatus(d.riskLevel)} className="mt-2" />
                  </div>
                ))}
                {(data?.devices?.external || []).length === 0 && <p>No external devices.</p>}
              </div>
            </div>
          )}

          {activeTab === 'Network' && (
            <div>
              {data?.network ? (
                <div className="space-y-1 text-sm">
                  <div><b>IP Address:</b> {data.network.ipAddress || '-'}</div>
                  <div><b>Gateway:</b> {data.network.gateway || '-'}</div>
                  <div><b>DNS:</b> {Array.isArray(data.network.dns) ? data.network.dns.join(', ') : '-'}</div>
                  <div><b>Active Connections:</b> {data.network.activeConnections ?? '-'}</div>
                </div>
              ) : (
                <p>No network snapshot.</p>
              )}
            </div>
          )}

          {activeTab === 'Domain Activity' && (
            <div className="space-y-2">
              {(data?.domainActivity || []).map((d, idx) => (
                <div key={`${d.domain}-${idx}`} className="border rounded-lg p-3 flex items-center justify-between">
                  <div>
                    <div className="font-semibold">{d.domain}</div>
                    <div className="text-sm text-[var(--color-gray-600)]">Requests: {d.requestCount} | Last: {d.lastAccessed || '-'}</div>
                  </div>
                  <StatusBadge status={normalizeStatus(d.riskLevel)} />
                </div>
              ))}
              {(data?.domainActivity || []).length === 0 && <p>No domain activity.</p>}
            </div>
          )}

          {activeTab === 'Terminal Events' && (
            <div className="space-y-2">
              {(data?.terminalEvents || []).map((e, idx) => (
                <div key={`${e.eventType}-${idx}`} className="border rounded-lg p-3">
                  <div className="font-semibold">{e.eventType} - {e.tool || '-'}</div>
                  <div className="text-sm text-[var(--color-gray-600)]">Command: {e.fullCommand || '-'}</div>
                  <div className="text-sm text-[var(--color-gray-600)]">Remote: {e.remoteIp || '-'} | Detected: {e.detectedAt || '-'}</div>
                  <StatusBadge status={normalizeStatus(e.riskLevel)} className="mt-2" />
                </div>
              ))}
              {(data?.terminalEvents || []).length === 0 && <p>No terminal events.</p>}
            </div>
          )}

          {activeTab === 'Browser History' && (
            <div className="space-y-2">
              {(data?.browserHistory || []).map((h, idx) => (
                <div key={`${h.url}-${idx}`} className="border rounded-lg p-3">
                  <div className="font-semibold break-all">{h.url}</div>
                  <div className="text-sm text-[var(--color-gray-600)]">{h.title || '-'}</div>
                  <div className="text-sm text-[var(--color-gray-600)]">Visits: {h.visitCount || 0} | Last Visit: {h.lastVisit || '-'}</div>
                </div>
              ))}
              {(data?.browserHistory || []).length === 0 && <p>No browser history.</p>}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
