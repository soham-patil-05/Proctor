const API_BASE = import.meta.env.VITE_API_BASE;

const handleResponse = async (response) => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.error || 'Request failed');
  }
  return response.json();
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
