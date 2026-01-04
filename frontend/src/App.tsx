import "./App.css"

import { useStytchMemberSession } from "@stytch/react/b2b"
import { lazy, Suspense } from "react"
import { Navigate, Route, Routes } from "react-router-dom"

import { LoadingSpinner } from "./components/ui/loading-spinner"
import { SettingsSkeleton } from "./components/ui/skeleton"
import AppLayout from "./layouts/AppLayout"
import AuthCallback from "./pages/AuthCallback"
import Dashboard from "./pages/Dashboard"
import Login from "./pages/Login"

// Lazy-load settings pages for code splitting
const ProfileSettings = lazy(() => import("./pages/settings/ProfileSettings"))
const OrganizationSettings = lazy(
  () => import("./pages/settings/OrganizationSettings")
)
const MembersSettings = lazy(() => import("./pages/settings/MembersSettings"))
const BillingSettings = lazy(() => import("./pages/settings/BillingSettings"))

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, isInitialized } = useStytchMemberSession()

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized can be false
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
        <Route
          path="/settings/profile"
          element={
            <Suspense fallback={<SettingsSkeleton />}>
              <ProfileSettings />
            </Suspense>
          }
        />
        <Route
          path="/settings/organization"
          element={
            <Suspense fallback={<SettingsSkeleton />}>
              <OrganizationSettings />
            </Suspense>
          }
        />
        <Route
          path="/settings/members"
          element={
            <Suspense fallback={<SettingsSkeleton />}>
              <MembersSettings />
            </Suspense>
          }
        />
        <Route
          path="/settings/billing"
          element={
            <Suspense fallback={<SettingsSkeleton />}>
              <BillingSettings />
            </Suspense>
          }
        />
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
