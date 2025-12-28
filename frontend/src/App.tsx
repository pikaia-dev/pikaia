import { Routes, Route, Navigate } from 'react-router-dom'
import { useStytchMemberSession } from '@stytch/react/b2b'
import Login from './pages/Login'
import AuthCallback from './pages/AuthCallback'
import Dashboard from './pages/Dashboard'
import './App.css'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, isInitialized } = useStytchMemberSession()

  if (!isInitialized) {
    return <div className="loading">Loading...</div>
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
