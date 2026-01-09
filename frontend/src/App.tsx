import "./App.css"

import { useStytchMemberSession } from "@stytch/react/b2b"
import { lazy, Suspense, useEffect, useState } from "react"
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
const SecuritySettings = lazy(() => import("./pages/settings/SecuritySettings"))

// Basic ProtectedRoute component
// Enhanced to prevent "flash of login" by handling undefined session state
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, isInitialized } = useStytchMemberSession()
  const [waitingTimedOut, setWaitingTimedOut] = useState(false)

  // Check if we should wait for session (set during login flow)
  // Read from sessionStorage on each render to get current value
  const justLoggedIn =
    sessionStorage.getItem("stytch_just_logged_in") === "true"

  // Clear flag when session arrives
  useEffect(() => {
    if (session && justLoggedIn) {
      sessionStorage.removeItem("stytch_just_logged_in")
    }
  }, [session, justLoggedIn])

  // Timeout safety valve - only runs when waiting for session
  useEffect(() => {
    if (!justLoggedIn || session || waitingTimedOut) return

    const timer = setTimeout(() => {
      sessionStorage.removeItem("stytch_just_logged_in")
      setWaitingTimedOut(true)
    }, 5000) // 5s max wait time
    return () => {
      clearTimeout(timer)
    }
  }, [justLoggedIn, session, waitingTimedOut])

  // Derive waiting state from other values instead of syncing via setState
  const isWaitingForSession = justLoggedIn && !session && !waitingTimedOut

  // Wait for SDK initialization AND initial session check
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized can be false during SDK init
  if (!isInitialized || isWaitingForSession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <LoadingSpinner className="mx-auto" />
          {isWaitingForSession && (
            <p className="mt-4 text-sm text-muted-foreground">
              Signing you in...
            </p>
          )}
        </div>
      </div>
    )
  }

  // If initialized but no session, redirect to login
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
          path="/settings/security"
          element={
            <Suspense fallback={<SettingsSkeleton />}>
              <SecuritySettings />
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
