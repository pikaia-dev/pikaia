import "./App.css"

import { useStytchMemberSession } from "@stytch/react/b2b"
import { Navigate,Route, Routes } from "react-router-dom"

import { LoadingSpinner } from "./components/ui/loading-spinner"
import AppLayout from "./layouts/AppLayout"
import AuthCallback from "./pages/AuthCallback"
import Dashboard from "./pages/Dashboard"
import Login from "./pages/Login"
import BillingSettings from "./pages/settings/BillingSettings"
import MembersSettings from "./pages/settings/MembersSettings"
import OrganizationSettings from "./pages/settings/OrganizationSettings"
import ProfileSettings from "./pages/settings/ProfileSettings"

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, isInitialized } = useStytchMemberSession()

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    )
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

      {/* Authenticated routes with sidebar layout */}
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings/profile" element={<ProfileSettings />} />
        <Route
          path="/settings/organization"
          element={<OrganizationSettings />}
        />
        <Route path="/settings/members" element={<MembersSettings />} />
        <Route path="/settings/billing" element={<BillingSettings />} />
        <Route
          path="/settings"
          element={<Navigate to="/settings/profile" replace />}
        />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
