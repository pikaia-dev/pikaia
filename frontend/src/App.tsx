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

// Basic ProtectedRoute component
// Enhanced to prevent "flash of login" by handling undefined session state
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, isInitialized } = useStytchMemberSession()
  const [isWaitingForSession, setIsWaitingForSession] = useState(() => {
    // efficient lazy initialization
    return sessionStorage.getItem("stytch_just_logged_in") === "true"
  })

  useEffect(() => {
    if (session) {
      // Session found! Clear flag and stop waiting
      sessionStorage.removeItem("stytch_just_logged_in")
      setIsWaitingForSession(false)
    }
  }, [session])

  useEffect(() => {
    if (isWaitingForSession && isInitialized && !session) {
      // If we are waiting for session but it hasn't appeared yet, set a timeout safety valve
      const timer = setTimeout(() => {
        sessionStorage.removeItem("stytch_just_logged_in")
        setIsWaitingForSession(false)
      }, 5000) // 5s max wait time
      return () => { clearTimeout(timer); }
    }
  }, [isWaitingForSession, isInitialized, session])

  // Wait for SDK initialization AND initial session check
  // isInitialized only means the SDK is ready, not that we've checked for a session
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
          path="/settings"
          element={<Navigate to="/settings/profile" replace />}
        />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
