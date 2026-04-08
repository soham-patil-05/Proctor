import { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import { api } from '../services/api';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import InputField from '../components/ui/InputField';
import StatusBadge from '../components/ui/StatusBadge';
import Sidebar from '../components/layout/Sidebar';
import Topbar from '../components/layout/Topbar';
import { useSession } from '../context/SessionContext';

export default function MySubjects() {
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    department: '',
    year: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const teacherName = localStorage.getItem('teacherName') || 'Professor';
  const { liveSession } = useSession();

  useEffect(() => {
    loadSubjects();
  }, []);

  const loadSubjects = async () => {
    try {
      const data = await api.subjects.getAll();
      setSubjects(data);
    } catch (error) {
      console.error('Error loading subjects:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      await api.subjects.create({
        ...formData,
        year: parseInt(formData.year),
      });
      setModalOpen(false);
      setFormData({ name: '', department: '', year: '' });
      loadSubjects();
    } catch (error) {
      console.error('Error creating subject:', error);
      alert('Failed to create subject');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      <Sidebar />
      <div className="ml-64">
        <Topbar teacherName={teacherName} />
        <main className={`p-8 ${liveSession ? 'mt-28' : 'mt-16'}`}>
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <h1 className="text-3xl font-bold text-[var(--color-gray-900)] tracking-wide">
                My Subjects
              </h1>
              <Button
                variant="primary"
                onClick={() => setModalOpen(true)}
              >
                <Plus className="h-5 w-5 mr-2" />
                Create Subject
              </Button>
            </div>

            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[1, 2, 3].map((i) => (
                  <Card key={i} className="p-6 animate-pulse">
                    <div className="h-4 bg-[var(--color-gray-200)] rounded w-3/4 mb-3"></div>
                    <div className="h-3 bg-[var(--color-gray-200)] rounded w-1/2"></div>
                  </Card>
                ))}
              </div>
            ) : subjects.length === 0 ? (
              <Card className="p-12 text-center">
                <p className="text-[var(--color-gray-600)] mb-4">
                  No subjects found. Create your first subject to get started.
                </p>
                <Button variant="primary" onClick={() => setModalOpen(true)}>
                  <Plus className="h-5 w-5 mr-2" />
                  Create Subject
                </Button>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {subjects.map((subject, index) => (
                  <Card
                    key={subject.id}
                    className="p-6 fade-in"
                    hoverable
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <h3 className="text-lg font-bold text-[var(--color-gray-900)]">
                        {subject.name}
                      </h3>
                      <StatusBadge status={subject.active ? 'active' : 'inactive'} />
                    </div>
                    <div className="space-y-2 text-sm text-[var(--color-gray-600)]">
                      <p>
                        <span className="font-medium">Department:</span> {subject.department}
                      </p>
                      <p>
                        <span className="font-medium">Year:</span> {subject.year}
                      </p>
                      <p>
                        <span className="font-medium">Total Sessions:</span>{' '}
                        {subject.totalSessions || 0}
                      </p>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </main>
      </div>

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Create New Subject"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              loading={submitting}
              disabled={submitting}
            >
              Create
            </Button>
          </>
        }
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <InputField
            label="Subject Name"
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., Operating Systems Lab"
            required
          />
          <InputField
            label="Department"
            type="text"
            value={formData.department}
            onChange={(e) => setFormData({ ...formData, department: e.target.value })}
            placeholder="e.g., CS"
            required
          />
          <InputField
            label="Year"
            type="number"
            value={formData.year}
            onChange={(e) => setFormData({ ...formData, year: e.target.value })}
            placeholder="e.g., 3"
            required
            min="1"
            max="5"
          />
        </form>
      </Modal>
    </div>
  );
}
