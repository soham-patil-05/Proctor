import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import StudentDetail from './pages/StudentDetail'

function App() {
  return (
    <Router>
      <div className="app">
        <header className="app-header">
          <h1>🛡️ Lab Guardian - Teacher Dashboard</h1>
          <div className="header-info">
            <span className="status-indicator">
              <span className="dot green"></span> Online
            </span>
          </div>
        </header>
        
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/student/:sessionId" element={<StudentDetail />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
