import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, SlidersHorizontal, ChevronRight, Users, FlaskConical } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import InputField from '../components/ui/InputField';
import { LAB_LIST } from '../constants/labs';
import { queryStudents } from '../services/api';
import { toast } from '../components/ui/Toast';

// ─── URL ↔ form helpers ───────────────────────────────────────────────────────

function formFromParams(params) {
  return {
    sessionId: params.get('sessionId') || '',
    startTime: params.get('startTime') || '',
    endTime: params.get('endTime') || '',
    labNo: params.get('labNo') || 'All',
    rollNoStart: params.get('rollNoStart') || '',
    rollNoEnd: params.get('rollNoEnd') || '',
  };
}

function paramsFromForm(form) {
  const p = new URLSearchParams();
  if (form.sessionId) p.set('sessionId', form.sessionId);
  if (form.startTime) p.set('startTime', form.startTime);
  if (form.endTime) p.set('endTime', form.endTime);
  if (form.labNo && form.labNo !== 'All') p.set('labNo', form.labNo);
  if (form.rollNoStart) p.set('rollNoStart', form.rollNoStart);
  if (form.rollNoEnd) p.set('rollNoEnd', form.rollNoEnd);
  return p;
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="divide-y divide-[var(--color-gray-100)]">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="px-5 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="skeleton h-9 w-9 rounded-lg" />
            <div className="space-y-2">
              <div className="skeleton h-4 w-36 rounded" />
              <div className="skeleton h-3 w-52 rounded" />
            </div>
          </div>
          <div className="skeleton h-5 w-5 rounded" />
        </div>
      ))}
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function FilterPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [form, setForm] = useState(() => formFromParams(searchParams));
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // cache key so we don't re-fetch on back navigation
  const lastFetchKey = useRef('');

  // Build a stable cache key from form values
  const buildKey = (f) =>
    [f.sessionId, f.startTime, f.endTime, f.labNo, f.rollNoStart, f.rollNoEnd].join('|');

  // On mount: if URL already has sessionId, restore and re-fetch if stale
  useEffect(() => {
    const urlForm = formFromParams(searchParams);
    if (!urlForm.sessionId) return;

    const key = buildKey(urlForm);
    // Only fetch if not already cached
    if (lastFetchKey.current === key) return;

    setForm(urlForm);
    fetchData(urlForm);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onChange = useCallback((key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError('');
  }, []);

  const fetchData = async (f) => {
    const sessionId = f.sessionId.trim();
    if (!sessionId) {
      setError('Session ID is required.');
      return;
    }

    let rollNoStart = f.rollNoStart.trim() || undefined;
    let rollNoEnd = f.rollNoEnd.trim() || undefined;
    // Both must be present or neither
    if (!rollNoStart || !rollNoEnd) {
      rollNoStart = undefined;
      rollNoEnd = undefined;
    }

    const params = {
      sessionId,
      ...(f.startTime ? { startTime: f.startTime } : {}),
      ...(f.endTime ? { endTime: f.endTime } : {}),
      ...(f.labNo && f.labNo !== 'All' ? { labNo: f.labNo } : {}),
      ...(rollNoStart ? { rollNoStart, rollNoEnd } : {}),
    };

    const key = buildKey(f);
    setLoading(true);
    setHasSearched(true);
    try {
      const result = await queryStudents(params);
      const data = result.data || [];
      setRows(data);
      lastFetchKey.current = key;
      // Persist to URL
      setSearchParams(paramsFromForm(f), { replace: true });
      if (data.length === 0) toast.info('No records match the selected filters.');
      else toast.success(`${data.length} student${data.length !== 1 ? 's' : ''} found.`);
    } catch (err) {
      setError(err.message || 'Query failed');
      setRows([]);
      toast.error(err.message || 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  const onSearch = (e) => {
    e.preventDefault();
    fetchData(form);
  };

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        (r.rollNo || '').toLowerCase().includes(q) ||
        (r.name || '').toLowerCase().includes(q) ||
        (r.labNo || '').toLowerCase().includes(q)
    );
  }, [rows, searchQuery]);

  const hasFilters = form.startTime || form.endTime || (form.labNo && form.labNo !== 'All') || form.rollNoStart || form.rollNoEnd;

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      {/* Top nav */}
      <header className="bg-[var(--color-primary)] shadow-md">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="h-8 w-8 bg-white/10 rounded-lg flex items-center justify-center">
            <FlaskConical size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-white font-bold text-lg leading-none">Lab Guardian</h1>
            <p className="text-white/50 text-xs mt-0.5">Telemetry Monitor</p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-7">
        {/* Filter card */}
        <Card className="mb-5 overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--color-gray-100)] flex items-center gap-2">
            <SlidersHorizontal size={16} className="text-[var(--color-gray-500)]" />
            <span className="font-semibold text-sm text-[var(--color-gray-700)]">Filter Sessions</span>
            {hasFilters && (
              <span className="ml-auto text-xs text-[var(--color-accent)] font-medium cursor-pointer hover:underline"
                onClick={() => {
                  const reset = { sessionId: form.sessionId, startTime: '', endTime: '', labNo: 'All', rollNoStart: '', rollNoEnd: '' };
                  setForm(reset);
                }}>
                Clear filters
              </span>
            )}
          </div>

          <form onSubmit={onSearch} className="p-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <InputField
                label="Session ID"
                id="sessionId"
                value={form.sessionId}
                onChange={(e) => onChange('sessionId', e.target.value)}
                placeholder="e.g. SESS-2024-001"
                required
                hint="Required to fetch telemetry"
              />

              <div>
                <label className="block text-xs font-semibold text-[var(--color-gray-600)] uppercase tracking-wide mb-1.5">
                  Lab No.
                </label>
                <select
                  value={form.labNo}
                  onChange={(e) => onChange('labNo', e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--color-gray-300)] text-sm
                    bg-white hover:border-[var(--color-gray-400)]
                    focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-opacity-20 focus:outline-none
                    transition-all duration-150 text-[var(--color-gray-800)]"
                >
                  <option value="All">All Labs</option>
                  {LAB_LIST.map((lab) => (
                    <option key={lab} value={lab}>{lab}</option>
                  ))}
                </select>
              </div>

              <InputField
                label="Roll No. From"
                id="rollNoStart"
                value={form.rollNoStart}
                onChange={(e) => onChange('rollNoStart', e.target.value)}
                placeholder="e.g. 220101"
                hint="Both fields required for range"
              />

              <InputField
                label="Roll No. To"
                id="rollNoEnd"
                value={form.rollNoEnd}
                onChange={(e) => onChange('rollNoEnd', e.target.value)}
                placeholder="e.g. 220150"
              />

              <InputField
                label="Start Time"
                id="startTime"
                type="datetime-local"
                value={form.startTime}
                onChange={(e) => onChange('startTime', e.target.value)}
              />

              <InputField
                label="End Time"
                id="endTime"
                type="datetime-local"
                value={form.endTime}
                onChange={(e) => onChange('endTime', e.target.value)}
              />
            </div>

            {error && (
              <div className="mt-4 px-4 py-3 bg-[var(--color-error-bg)] border border-[var(--color-error)] border-opacity-30 rounded-lg flex items-center gap-2 text-sm text-[var(--color-error)]">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" className="shrink-0">
                  <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 4zm0 8a1 1 0 110-2 1 1 0 010 2z"/>
                </svg>
                {error}
              </div>
            )}

            <div className="mt-5 flex justify-end">
              <Button type="submit" loading={loading} disabled={loading} icon={Search} size="md">
                {loading ? 'Searching…' : 'Search'}
              </Button>
            </div>
          </form>
        </Card>

        {/* Results */}
        <Card className="overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--color-gray-100)] flex items-center gap-2">
            <Users size={16} className="text-[var(--color-gray-500)]" />
            <span className="font-semibold text-sm text-[var(--color-gray-700)]">Students</span>
            {rows.length > 0 && (
              <span className="ml-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-[var(--color-accent-subtle)] text-[var(--color-accent)]">
                {rows.length}
              </span>
            )}
            {rows.length > 4 && (
              <div className="ml-auto">
                <div className="relative">
                  <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-gray-400)]" />
                  <input
                    type="text"
                    placeholder="Filter results…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 pr-3 py-1.5 text-xs border border-[var(--color-gray-300)] rounded-lg
                      focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-opacity-20 focus:border-[var(--color-accent)]
                      bg-white w-44 transition-all duration-150"
                  />
                </div>
              </div>
            )}
          </div>

          {loading ? (
            <TableSkeleton />
          ) : !hasSearched ? (
            <div className="px-5 py-14 text-center">
              <div className="mx-auto h-12 w-12 rounded-full bg-[var(--color-gray-100)] flex items-center justify-center mb-3">
                <Search size={22} className="text-[var(--color-gray-400)]" />
              </div>
              <p className="text-sm font-medium text-[var(--color-gray-600)]">Enter a Session ID and search</p>
              <p className="text-xs text-[var(--color-gray-400)] mt-1">Results will appear here</p>
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="px-5 py-14 text-center">
              <div className="mx-auto h-12 w-12 rounded-full bg-[var(--color-gray-100)] flex items-center justify-center mb-3">
                <Users size={22} className="text-[var(--color-gray-400)]" />
              </div>
              <p className="text-sm font-medium text-[var(--color-gray-600)]">
                {searchQuery ? 'No students match your filter' : 'No students found'}
              </p>
              <p className="text-xs text-[var(--color-gray-400)] mt-1">
                {searchQuery ? 'Try a different search term' : 'Try adjusting the filter criteria'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--color-gray-100)] fade-in">
              {filteredRows.map((r) => (
                <button
                  key={`${r.sessionId}-${r.rollNo}`}
                  className="w-full text-left px-5 py-4 flex items-center gap-3 group
                    hover:bg-[var(--color-gray-50)] transition-colors duration-100"
                  onClick={() =>
                    navigate(
                      `/student/${encodeURIComponent(r.rollNo)}?sessionId=${encodeURIComponent(r.sessionId)}`
                    )
                  }
                >
                  <div className="h-9 w-9 rounded-lg bg-[var(--color-primary-subtle)] flex items-center justify-center shrink-0 text-xs font-bold text-[var(--color-primary)] group-hover:bg-[var(--color-primary)] group-hover:text-white transition-colors duration-150">
                    {(r.rollNo || '?').slice(-2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm text-[var(--color-gray-900)] truncate">
                      {r.rollNo}
                      {r.name ? <span className="font-normal text-[var(--color-gray-500)] ml-1.5">— {r.name}</span> : null}
                    </div>
                    <div className="text-xs text-[var(--color-gray-400)] mt-0.5 flex items-center gap-2">
                      <span>Lab: <span className="font-medium text-[var(--color-gray-600)]">{r.labNo || 'N/A'}</span></span>
                      <span className="text-[var(--color-gray-300)]">·</span>
                      <span>Last: {r.lastRecordedAt || 'N/A'}</span>
                    </div>
                  </div>
                  <ChevronRight
                    size={16}
                    className="text-[var(--color-gray-300)] group-hover:text-[var(--color-gray-500)] shrink-0 transition-colors duration-150"
                  />
                </button>
              ))}
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
