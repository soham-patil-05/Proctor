import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import Button from '../components/ui/Button';
import InputField from '../components/ui/InputField';
import Card from '../components/ui/Card';

export default function Login() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await api.auth.login(formData.email, formData.password);
      localStorage.setItem('token', response.token);
      localStorage.setItem('teacherName', response.teacherName);
      navigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Invalid credentials');
      setShake(true);
      setTimeout(() => setShake(false), 500);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-primary-light)] flex items-center justify-center px-4">
      <Card className={`w-full max-w-md p-8 ${shake ? 'shake' : ''}`}>
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-[var(--color-primary)] rounded-xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-2xl">L</span>
          </div>
          <h1 className="text-2xl font-bold text-[var(--color-gray-900)] mb-2">
            Lab Monitoring System
          </h1>
          <p className="text-[var(--color-gray-600)]">Teacher Portal</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <InputField
            label="Email"
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            placeholder="teacher@college.edu"
            required
          />

          <InputField
            label="Password"
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••••"
            required
          />

          {error && (
            <div className="bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] text-[var(--color-error)] px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            className="w-full"
            loading={loading}
            disabled={loading}
          >
            Login
          </Button>

          <div className="text-center flex items-center justify-center gap-4">
            <a href="#" className="text-sm text-[var(--color-accent)] hover:underline">
              Forgot password?
            </a>
            <span className="text-[var(--color-gray-400)]">|</span>
            <a href="/register" className="text-sm text-[var(--color-accent)] hover:underline">
              Register
            </a>
          </div>
        </form>
      </Card>
    </div>
  );
}
