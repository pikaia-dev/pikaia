import { useStytchMemberSession } from "@stytch/react/b2b"
import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

import { LoadingSpinner } from "../components/ui/loading-spinner"
import {
  CheckEmailScreen,
  EmailLoginForm,
  GoogleOAuthButton,
  OrganizationSelector,
} from "../features/auth/components"
import { useDiscoveryAuth } from "../features/auth/hooks"

export default function Login() {
  const navigate = useNavigate()
  const { session, isInitialized } = useStytchMemberSession()
  const {
    state,
    sendMagicLink,
    startGoogleOAuth,
    exchangeSession,
    resetToEmail,
  } = useDiscoveryAuth()

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized can be false
    if (isInitialized && session) {
      // eslint-disable-next-line @typescript-eslint/no-floating-promises -- navigate returns void
      navigate("/dashboard", { replace: true })
    }
  }, [session, isInitialized, navigate])

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized and session can change
  if (!isInitialized || session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm p-8">
        {state.step === "email" && (
          <>
            <div className="text-center mb-6">
              <h1 className="text-2xl font-semibold tracking-tight">
                Welcome back
              </h1>
              <p className="text-sm text-muted-foreground mt-2">
                Sign in with Google or enter your email
              </p>
            </div>

            <div className="space-y-4">
              <GoogleOAuthButton
                onClick={startGoogleOAuth}
                isLoading={state.isLoading}
              />

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-2 text-muted-foreground">
                    Or continue with
                  </span>
                </div>
              </div>

              <EmailLoginForm
                onSubmit={sendMagicLink}
                isLoading={state.isLoading}
                error={state.error}
              />
            </div>
          </>
        )}

        {state.step === "check-email" && (
          <CheckEmailScreen email={state.email} onBack={resetToEmail} />
        )}

        {state.step === "select-org" && (
          <OrganizationSelector
            organizations={state.discoveredOrganizations}
            onSelect={exchangeSession}
            onBack={resetToEmail}
            isLoading={state.isLoading}
            error={state.error}
            email={state.email}
          />
        )}
      </div>
    </div>
  )
}
