import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Clock, Filter, RefreshCw, Key } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import InputField from '../components/ui/InputField';

const API_BASE = import.meta.env.VITE_API_BASE;

export default function ExamDashboard() {
  const navigate = useNavigate();
  const [students, setStudents] = useState([]);
  const [groupedStudents, setGroupedStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    lab_no: '',
    time_from: '',
    time_to: ''
  });
  const [showEndModal, setShowEndModal] = useState(false);
  const [secretKey, setSecretKey] = useState('');
  const [refreshInterval, setRefreshInterval] = useState(null);

  // Fetch students data
  const fetchStudents = async () => {
    try {
      const params = new URLSearchParams();
      if (filters.lab_no) params.append('lab_no', filters.lab_no);
      if (filters.time_from) params.append('time_from', filters.time_from);
      if (filters.time_to) params.append('time_to', filters.time_to);

      const response = await fetch(`${API_BASE}/dashboard/students?${params}`);
      const data = await response.json();
      
      setGroupedStudents(data.grouped || []);
      setStudents(data.grouped?.flatMap(g => g.students) || []);
    } catch (error) {
      console.error('Error fetching students:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStudents();

    // Auto-refresh every 10 seconds
    setRefreshInterval(setInterval(fetchStudents, 10000));

    return () => {
      if (refreshInterval) clearInterval(refreshInterval);
    };
  }, [filters]);

  // Handle filter changes
  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({ lab_no: '', time_from: '', time_to: '' });
  };

  // End all sessions
  const handleEndAllSessions = async () => {
    try {
      const response = await fetch(`${API_BASE}/exam/end-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret_key: secretKey })
      });

      const data = await response.json();

      if (response.ok) {
        alert(`Successfully ended ${data.ended_count} session(s)`);
        setShowEndModal(false);
        setSecretKey('');
        fetchStudents();
      } else {
        alert(data.error || 'Failed to end sessions');
      }
    } catch (error) {
      console.error('Error ending sessions:', error);
      alert('Failed to end sessions');
    }
  };

  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    });
  };

  // Calculate duration
  const getDuration = (startTime) => {
    if (!startTime) return '-';
    const elapsed = (Date.now() / 1000) - startTime;
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const seconds = Math.floor(elapsed % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                🛡️ Lab Guardian - Exam Dashboard
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                Monitoring {students.length} active student(s)
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={fetchStudents}
                variant="outline"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
              <Button
                onClick={() => setShowEndModal(true)}
                variant="danger"
              >
                <Key className="h-4 w-4 mr-2" />
                End All Sessions
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Filters */}
        <Card className="p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="h-5 w-5 text-gray-700" />
            <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Lab Number
              </label>
              <select
                value={filters.lab_no}
                onChange={(e) => handleFilterChange('lab_no', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Labs</option>
                {Array.from({ length: 12 }, (_, i) => `L${(i + 1).toString().padStart(2, '0')}`).map(lab => (
                  <option key={lab} value={lab}>{lab}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Time From
              </label>
              <input
                type="datetime-local"
                value={filters.time_from}
                onChange={(e) => handleFilterChange('time_from', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Time To
              </label>
              <input
                type="datetime-local"
                value={filters.time_to}
                onChange={(e) => handleFilterChange('time_to', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={clearFilters}
                variant="outline"
                className="w-full"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </Card>

        {/* Students Grouped by Start Time */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading students...</p>
          </div>
        ) : groupedStudents.length === 0 ? (
          <Card className="p-12 text-center">
            <Users className="h-16 w-16 mx-auto text-gray-300 mb-4" />
            <h3 className="text-xl font-semibold text-gray-700 mb-2">No Active Students</h3>
            <p className="text-gray-500">Students will appear here when they start their exam</p>
          </Card>
        ) : (
          <div className="space-y-6">
            {groupedStudents.map((group, index) => (
              <div key={index}>
                <div className="flex items-center gap-2 mb-3">
                  <Clock className="h-5 w-5 text-blue-600" />
                  <h3 className="text-lg font-semibold text-gray-900">
                    Started at {formatTime(group.students[0]?.start_time)} - {formatDate(group.students[0]?.start_time)}
                  </h3>
                  <span className="text-sm text-gray-500">
                    ({group.students.length} student{group.students.length !== 1 ? 's' : ''})
                  </span>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {group.students.map((student) => (
                    <Card
                      key={student.session_id}
                      className="p-5 hover:shadow-lg transition-shadow cursor-pointer"
                      onClick={() => navigate(`/student/${student.session_id}`)}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h4 className="text-lg font-bold text-gray-900">
                            {student.roll_no}
                          </h4>
                          <p className="text-sm text-gray-600">
                            Lab: {student.lab_no}
                          </p>
                        </div>
                        <span className="px-2 py-1 text-xs font-semibold bg-green-100 text-green-800 rounded-full">
                          Active
                        </span>
                      </div>

                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Started:</span>
                          <span className="font-medium">{formatTime(student.start_time)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Duration:</span>
                          <span className="font-medium text-blue-600">
                            {getDuration(student.start_time)}
                          </span>
                        </div>
                      </div>

                      <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-2 gap-3 text-xs">
                        <div className="text-center">
                          <div className="text-lg font-bold text-gray-900">
                            {student.process_count}
                          </div>
                          <div className="text-gray-600">Processes</div>
                        </div>
                        <div className="text-center">
                          <div className="text-lg font-bold text-gray-900">
                            {student.browser_history_count}
                          </div>
                          <div className="text-gray-600">URLs</div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* End Session Modal */}
      <Modal
        isOpen={showEndModal}
        onClose={() => {
          setShowEndModal(false);
          setSecretKey('');
        }}
        title="End All Exam Sessions"
      >
        <div className="space-y-4">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-sm text-yellow-800">
              ⚠️ Warning: This will end all active exam sessions. Students will not be able to continue.
            </p>
          </div>
          
          <InputField
            label="Enter Secret Key"
            type="password"
            value={secretKey}
            onChange={(e) => setSecretKey(e.target.value)}
            placeholder="Enter secret key..."
          />

          <div className="flex gap-3">
            <Button
              onClick={() => {
                setShowEndModal(false);
                setSecretKey('');
              }}
              variant="outline"
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleEndAllSessions}
              variant="danger"
              className="flex-1"
              disabled={!secretKey}
            >
              End All Sessions
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
