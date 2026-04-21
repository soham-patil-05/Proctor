const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/+$/, '');

const parseApiPayload = async (response) => {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  const snippet = text.slice(0, 80).replace(/\s+/g, ' ').trim();
  throw new Error(`Expected JSON response but received non-JSON content: ${snippet || 'empty body'}`);
};

const handleResponse = async (response) => {
  if (!response.ok) {
    const payload = await parseApiPayload(response).catch(() => ({ error: 'Request failed' }));
    throw new Error(payload.error || 'Request failed');
  }
  return parseApiPayload(response);
};

const toQueryString = (params = {}) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') search.set(k, String(v));
  });
  return search.toString();
};

export async function queryStudents(params) {
  const query = toQueryString(params);
  const response = await fetch(`${API_BASE}/telemetry/query?${query}`, {
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(response);
}

export async function getStudentDetail(rollNo, sessionId) {
  const query = toQueryString({ sessionId });
  const response = await fetch(`${API_BASE}/telemetry/student/${encodeURIComponent(rollNo)}?${query}`, {
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(response);
}
