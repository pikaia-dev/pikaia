import { useStytchMemberSession } from '@stytch/react/b2b'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { OrganizationSelector } from '@/features/auth/components/organization-selector'
import { useAuthCallback } from '@/features/auth/hooks/use-auth-callback'

/**
 * Auth callback handles Stytch redirects after magic link clicks and OAuth.
 * Uses useAuthCallback hook for all auth flow logic.
 */
export default function AuthCallback() {
  const { session, isInitialized } = useStytchMemberSession()
  const navigate = useNavigate()

  const { state, exchangeSession, goToLogin } = useAuthCallback({
    onRedirectToLogin: () => {
      void navigate('/login', { replace: true })
    },
  })

  // Redirect to dashboard when session is established
  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized can be false during SDK init
    if (isInitialized && session) {
      window.location.href = '/dashboard'
    }
  }, [session, isInitialized])

  // Show org selector for multi-org users
  if (state.showOrgSelector) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="w-full max-w-sm p-8">
          <OrganizationSelector
            organizations={state.discoveredOrgs}
            onSelect={exchangeSession}
            onBack={goToLogin}
            isLoading={state.isLoading}
            error={state.error}
            email={state.email}
          />
        </div>
      </div>
    )
  }

  // Show error state
  if (state.error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <p className="text-destructive mb-4">{state.error}</p>
          <button
            type="button"
            onClick={goToLogin}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Back to login
          </button>
        </div>
      </div>
    )
  }

  // Loading state
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <LoadingSpinner className="mx-auto" />
        <p className="mt-4 text-sm text-muted-foreground">Signing you in...</p>
      </div>
    </div>
  )
}
