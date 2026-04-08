const API_BASE = import.meta.env.VITE_API_BASE;

const getToken = () => {
  return localStorage.getItem('token');
};

const handleResponse = async (response) => {
  if (response.status === 401) {
    localStorage.removeItem('token');
    localStorage.removeItem('teacherName');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Network error' }));
    throw new Error(error.error || 'Request failed');
  }

  return response.json();
};

export const api = {
  auth: {
    login: async (email, password) => {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });
      return handleResponse(response);
    },
    register: async(name,email,password)=>{
      const response = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name,email, password }),
      });
      return handleResponse(response);
    }
  },

  subjects: {
    getAll: async () => {
      const response = await fetch(`${API_BASE}/teacher/subjects`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },

    create: async (subjectData) => {
      const response = await fetch(`${API_BASE}/teacher/subjects`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(subjectData),
      });
      return handleResponse(response);
    },
  },

  sessions: {
    create: async (sessionData) => {
      const response = await fetch(`${API_BASE}/teacher/sessions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(sessionData),
      });
      return handleResponse(response);
    },

    getAll: async (status = 'all') => {
      const response = await fetch(`${API_BASE}/teacher/sessions?status=${status}`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },

    getById: async (sessionId) => {
      const response = await fetch(`${API_BASE}/teacher/sessions/${sessionId}`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },

    end: async (sessionId) => {
      const response = await fetch(`${API_BASE}/teacher/sessions/${sessionId}/end`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });
      return handleResponse(response);
    },

    getStudents: async (sessionId) => {
      const response = await fetch(`${API_BASE}/teacher/sessions/${sessionId}/students`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },
  },

  students: {
    getById: async (rollNo) => {
      const response = await fetch(`${API_BASE}/teacher/students/${rollNo}`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },

    getDevices: async (rollNo) => {
      const response = await fetch(`${API_BASE}/teacher/students/${rollNo}/devices`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },

    getNetwork: async (rollNo) => {
      const response = await fetch(`${API_BASE}/teacher/students/${rollNo}/network`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },

    getDomainActivity: async (rollNo) => {
      const response = await fetch(`${API_BASE}/teacher/students/${rollNo}/domain-activity`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
      });
      return handleResponse(response);
    },
  },
};
