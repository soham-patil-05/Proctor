import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import Button from '../components/ui/Button';
import SearchBar from '../components/ui/SearchBar';
import Modal from '../components/ui/Modal';
import Sidebar from '../components/layout/Sidebar';
import Topbar from '../components/layout/Topbar';
import StudentListItem from '../components/session/StudentListItem';
import { useSession } from '../context/SessionContext';

export default function LiveSession() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const pollRef = useRef(null);
  const [session, setSession] = useState(null);
  const [students, setStudents] = useState([]);
  const [filteredStudents, setFilteredStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [endModalOpen, setEndModalOpen] = useState(false);
  const [ending, setEnding] = useState(false);
  const [elapsed, setElapsed] = useState('00:00:00');
  const teacherName = localStorage.getItem('teacherName') || 'Professor';
  const { liveSession, endSession } = useSession();

  useEffect(() => {
    if (!session?.date || !session?.startTime) return;
    const datePart = session.date.substring(0, 10);
    const startMs = new Date(`${datePart}T${session.startTime}`).getTime();
    if (Number.isNaN(startMs)) return;

    const fmt = (totalSec) => {
      const h = Math.floor(totalSec / 3600);
      const m = Math.floor((totalSec % 3600) / 60);
      const s = totalSec % 60;
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    };

    // Session ended — show fixed duration
    if (!session.isLive && session.endTime) {
      const endMs = new Date(session.endTime).getTime();
      setElapsed(fmt(Math.max(0, Math.floor((endMs - startMs) / 1000))));
      return;
    }

    // Session live — tick every second
    const update = () => setElapsed(fmt(Math.max(0, Math.floor((Date.now() - startMs) / 1000))));
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [session?.date, session?.startTime, session?.isLive, session?.endTime]);

  useEffect(() => {
    loadSessionData();

    // Poll session + students every 5 s
    pollRef.current = setInterval(async () => {
      try {
        const [sessionData, studentsData] = await Promise.all([
          api.sessions.getById(sessionId),
          api.sessions.getStudents(sessionId),
        ]);
        setSession(sessionData);
        setStudents(studentsData);
        setFilteredStudents(studentsData);
      } catch {
        // silently ignore poll errors
      }
    }, 5000);

    return () => clearInterval(pollRef.current);
  }, [sessionId, location.key]);

  const loadSessionData = async () => {
    try {
      const [sessionData, studentsData] = await Promise.all([
        api.sessions.getById(sessionId),
        api.sessions.getStudents(sessionId),
      ]);

      setSession(sessionData);
      setStudents(studentsData);
      setFilteredStudents(studentsData);
    } catch (error) {
      console.error('Error loading session:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = useCallback((query) => {
    if (!query.trim()) {
      setFilteredStudents(students);
      return;
    }

    const filtered = students.filter((student) =>
      student.rollNo.toLowerCase().includes(query.toLowerCase())
    );
    setFilteredStudents(filtered);
  }, [students]);

  const handleEndSession = async () => {
    setEnding(true);
    try {
      await api.sessions.end(sessionId);
      endSession();
      setEndModalOpen(false);
      navigate('/sessions');
    } catch (error) {
      console.error('Error ending session:', error);
      alert('Failed to end session');
    } finally {
      setEnding(false);
    }
  };

  const handleStudentClick = (student) => {
    navigate(`/student/${student.rollNo}?sessionId=${sessionId}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--color-gray-50)] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-primary)] mx-auto"></div>
          <p className="mt-4 text-[var(--color-gray-600)]">Loading session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-gray-50)]">
      <Sidebar />
      <div className="ml-64">
        <Topbar teacherName={teacherName} hideBanner />
        <main className="p-8 mt-16">
          <div className="max-w-7xl mx-auto">
            <div className="bg-white rounded-lg shadow-md p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h1 className="text-2xl font-bold text-[var(--color-gray-900)]">
                  {session?.subjectName}
                </h1>
                {session?.isLive && (
                  <Button variant="danger" onClick={() => setEndModalOpen(true)}>
                    End Session
                  </Button>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mb-4 text-sm text-[var(--color-gray-700)]">
                <span>
                  <span className="font-semibold">Session ID:</span> {sessionId}
                </span>
                <span className="text-[var(--color-gray-400)]">|</span>
                <span>
                  <span className="font-semibold">Batch:</span> {session?.batch}
                </span>
                <span className="text-[var(--color-gray-400)]">|</span>
                <span>
                  <span className="font-semibold">Lab:</span> {session?.labName}
                </span>
                <span className="text-[var(--color-gray-400)]">|</span>
                <span className="flex items-center space-x-1">
                  <span className="font-semibold">Time:</span>
                  <span className={`font-mono font-semibold ${session?.isLive ? 'text-[var(--color-success)]' : 'text-red-600'}`}>{elapsed}</span>
                </span>
              </div>

              <SearchBar
                placeholder="Search by Roll No"
                onSearch={handleSearch}
                debounce={300}
              />
            </div>

            <div className="bg-white rounded-lg shadow-md overflow-hidden">
              <div className="px-6 py-4 bg-[var(--color-gray-50)] border-b border-[var(--color-gray-200)]">
                <h2 className="text-lg font-semibold text-[var(--color-gray-900)]">
                  Students ({filteredStudents.length})
                </h2>
              </div>

              {filteredStudents.length === 0 ? (
                <div className="p-12 text-center text-[var(--color-gray-600)]">
                  No students found
                </div>
              ) : (
                <div className="max-h-[600px] overflow-y-auto">
                  {filteredStudents.map((student) => (
                    <StudentListItem
                      key={student.rollNo}
                      student={student}
                      onClick={handleStudentClick}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </main>
      </div>

      <Modal
        isOpen={endModalOpen}
        onClose={() => setEndModalOpen(false)}
        title="End Session"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEndModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleEndSession}
              loading={ending}
              disabled={ending}
            >
              End Session
            </Button>
          </>
        }
      >
        <p className="text-[var(--color-gray-600)]">
          Are you sure you want to end this session? This action cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
