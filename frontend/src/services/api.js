// API service for Lab Guardian offline-first dashboard

const API_BASE = import.meta.env.VITE_API_BASE || '';

/**
 * Fetch all active students grouped by start time
 * @param {Object} filters - Optional filters
 * @param {string} filters.lab_no - Filter by lab number
 * @param {string} filters.time_from - Filter by start time
 * @param {string} filters.time_to - Filter by end time
 */
export async function fetchDashboardStudents(filters = {}) {
  const params = new URLSearchParams();
  
  if (filters.lab_no) params.append('lab_no', filters.lab_no);
  if (filters.time_from) params.append('time_from', filters.time_from);
  if (filters.time_to) params.append('time_to', filters.time_to);
  
  const response = await fetch(`${API_BASE}/api/dashboard/students?${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch students: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Fetch detailed activity for a specific student session
 * @param {string} sessionId - The session UUID
 */
export async function fetchStudentDetails(sessionId) {
  const response = await fetch(`${API_BASE}/api/dashboard/student/${sessionId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch student details: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * End all active exam sessions
 * @param {string} secretKey - The secret key (80085)
 */
export async function endAllSessions(secretKey) {
  const response = await fetch(`${API_BASE}/api/exam/end-all`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ secret_key: secretKey }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to end sessions');
  }
  
  return response.json();
}

/**
 * Check backend health
 */
export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}
