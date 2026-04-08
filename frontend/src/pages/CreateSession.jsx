import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import InputField from '../components/ui/InputField';
import Sidebar from '../components/layout/Sidebar';
import Topbar from '../components/layout/Topbar';
import { useSession } from '../context/SessionContext';

export default function CreateSession() {
  const navigate = useNavigate();
  const [subjects, setSubjects] = useState([]);
  const [formData, setFormData] = useState({
    subjectId: '',
    batch: '',
    lab: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const teacherName = localStorage.getItem('teacherName') || 'Professor';
  const { liveSession, startSession } = useSession();

  useEffect(() => {
    loadSubjects();
  }, []);

  const loadSubjects = async () => {
    try {
      const data = await api.subjects.getAll();
      setSubjects(data);
    } catch (error) {
      console.error('Error loading subjects:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const now = new Date();
      const date = now.toISOString().split('T')[0];
      const startTime = now.toTimeString().slice(0, 5); // HH:MM

      const response = await api.sessions.create({
        ...formData,
        date,
        startTime,
      });

      const selectedSubject = subjects.find((s) => s.id === formData.subjectId);
      startSession({
        sessionId: response.sessionId,
        subject: selectedSubject?.name,
        batch: formData.batch,
        status: 'live',
      });

      navigate(`/live-session/${response.sessionId}`);
    } catch (error) {
      console.error('Error creating session:', error);
      alert('Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      <Sidebar />
      <div className="ml-64">
        <Topbar teacherName={teacherName} />
        <main className={`p-8 ${liveSession ? 'mt-28' : 'mt-16'}`}>
          <div className="max-w-2xl mx-auto">
            <h1 className="text-3xl font-bold text-[var(--color-gray-900)] mb-8 tracking-wide">
              Create New Session
            </h1>

            <Card className="p-8">
              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-[var(--color-gray-700)] mb-1.5">
                    Subject <span className="text-[var(--color-error)]">*</span>
                  </label>
                  <select
                    value={formData.subjectId}
                    onChange={(e) =>
                      setFormData({ ...formData, subjectId: e.target.value })
                    }
                    required
                    className="w-full px-4 py-2.5 rounded-lg border border-[var(--color-gray-300)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] transition-all duration-200"
                  >
                    <option value="">Select a subject</option>
                    {subjects.map((subject) => (
                      <option key={subject.id} value={subject.id}>
                        {subject.name} - {subject.department} (Year {subject.year})
                      </option>
                    ))}
                  </select>
                </div>

                <InputField
                  label="Batch Name"
                  type="text"
                  value={formData.batch}
                  onChange={(e) => setFormData({ ...formData, batch: e.target.value })}
                  placeholder="e.g., Batch A"
                  required
                />

                <InputField
                  label="Lab Name"
                  type="text"
                  value={formData.lab}
                  onChange={(e) => setFormData({ ...formData, lab: e.target.value })}
                  placeholder="e.g., Lab 1"
                  required
                />

                <InputField
                  label="Password (Optional)"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="Session password for students"
                />

                <div className="flex space-x-4 pt-4">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => navigate('/dashboard')}
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    loading={loading}
                    disabled={loading}
                    className="flex-1"
                  >
                    Create Session
                  </Button>
                </div>
              </form>
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}
