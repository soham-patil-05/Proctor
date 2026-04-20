import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import InputField from '../components/ui/InputField';
import { LAB_LIST } from '../constants/labs';
import { queryStudents } from '../services/api';

export default function FilterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    sessionId: '',
    startTime: '',
    endTime: '',
    labNo: 'All',
    rollNoStart: '',
    rollNoEnd: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);

  const onChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError('');
  };

  const onSearch = async (e) => {
    e.preventDefault();
    if (!form.sessionId.trim()) {
      setError('Session ID is required.');
      return;
    }

    setLoading(true);
    try {
      const result = await queryStudents({
        sessionId: form.sessionId.trim(),
        startTime: form.startTime || undefined,
        endTime: form.endTime || undefined,
        labNo: form.labNo !== 'All' ? form.labNo : undefined,
        rollNoStart: form.rollNoStart || undefined,
        rollNoEnd: form.rollNoEnd || undefined,
      });
      setRows(result);
    } catch (err) {
      setError(err.message || 'Query failed');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)] p-6">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-6">Telemetry Filter</h1>

        <Card className="p-6 mb-6">
          <form onSubmit={onSearch} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InputField
              label="Session ID"
              value={form.sessionId}
              onChange={(e) => onChange('sessionId', e.target.value)}
              required
            />
            <div>
              <label className="block text-sm font-medium text-[var(--color-gray-700)] mb-1.5">Lab No.</label>
              <select
                value={form.labNo}
                onChange={(e) => onChange('labNo', e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-[var(--color-gray-300)]"
              >
                <option value="All">All</option>
                {LAB_LIST.map((lab) => (
                  <option key={lab} value={lab}>{lab}</option>
                ))}
              </select>
            </div>

            <InputField
              label="Start Timestamp"
              type="datetime-local"
              value={form.startTime}
              onChange={(e) => onChange('startTime', e.target.value)}
            />
            <InputField
              label="End Timestamp"
              type="datetime-local"
              value={form.endTime}
              onChange={(e) => onChange('endTime', e.target.value)}
            />

            <InputField
              label="Roll No. From"
              value={form.rollNoStart}
              onChange={(e) => onChange('rollNoStart', e.target.value)}
            />
            <InputField
              label="Roll No. To"
              value={form.rollNoEnd}
              onChange={(e) => onChange('rollNoEnd', e.target.value)}
            />

            {error && <p className="text-[var(--color-error)] text-sm md:col-span-2">{error}</p>}

            <div className="md:col-span-2">
              <Button type="submit" loading={loading} disabled={loading}>Search</Button>
            </div>
          </form>
        </Card>

        <Card className="p-0 overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--color-gray-200)] bg-white font-semibold">
            Students
          </div>
          {rows.length === 0 ? (
            <div className="p-6 text-[var(--color-gray-600)]">No records found.</div>
          ) : (
            <div className="divide-y divide-[var(--color-gray-200)]">
              {rows.map((r) => (
                <button
                  key={`${r.sessionId}-${r.rollNo}`}
                  className="w-full text-left px-6 py-4 hover:bg-[var(--color-gray-100)]"
                  onClick={() => navigate(`/student/${encodeURIComponent(r.rollNo)}?sessionId=${encodeURIComponent(r.sessionId)}`)}
                >
                  <div className="font-semibold text-[var(--color-gray-900)]">{r.rollNo} - {r.name || 'Unknown'}</div>
                  <div className="text-sm text-[var(--color-gray-600)]">Lab: {r.labNo || 'N/A'} | Last Recorded: {r.lastRecordedAt || 'N/A'}</div>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
