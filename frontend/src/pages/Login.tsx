import { useStytchMemberSession } from "@stytch/react/b2b"
import { Mail } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"


import { LoadingSpinner } from "../components/ui/loading-spinner"
import {
  CheckEmailScreen,
  EmailLoginForm,
  GoogleOAuthButton,
  OrganizationSelector,
  PasskeyLoginButton,
} from "../features/auth/components"
import { useDiscoveryAuth } from "../features/auth/hooks"
import {
  hasPasskeyHint,
  isWebAuthnSupported,
} from "../features/auth/hooks/usePasskeyAuth"

// Passkey placeholder token before Stytch session attestation
const PASSKEY_PLACEHOLDER_TOKEN = "passkey_authenticated"

// Props for the passkey-first login UI
interface PasskeyFirstLoginProps {
  onPasskeySuccess: (result: {
    session_token: string
    session_jwt: string
    member_id: string
    organization_id: string
    user_id: number
  }) => void
  startGoogleOAuth: () => void
  sendMagicLink: (email: string) => void
  isLoading: boolean
  error: string | null
}

/**
 * Component that shows passkey-first login for returning users,
 * or standard login for new users / users without passkeys.
 */
function PasskeyFirstLogin({
  onPasskeySuccess,
  startGoogleOAuth,
  sendMagicLink,
  isLoading,
  error,
}: PasskeyFirstLoginProps) {
  const [showAlternatives, setShowAlternatives] = useState(false)
  const showPasskeyFirst = isWebAuthnSupported() && hasPasskeyHint()

  // Passkey-first UI for returning users
  if (showPasskeyFirst && !showAlternatives) {
    return (
      <>
        <div className="text-center mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">
            Welcome back
          </h1>
          <p className="text-sm text-muted-foreground mt-2">
            Sign in with your passkey
          </p>
        </div>

        <div className="space-y-4">
          <PasskeyLoginButton
            onSuccess={onPasskeySuccess}
            variant="primary"
          />

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-background px-2 text-muted-foreground">
                Other sign in options
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <GoogleOAuthButton
              onClick={startGoogleOAuth}
              isLoading={isLoading}
            />
            <button
              type="button"
              onClick={() => setShowAlternatives(true)}
              className="w-full inline-flex items-center justify-center gap-2 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
            >
              <Mail className="h-4 w-4" />
              Continue with Email
            </button>
          </div>
        </div>
      </>
    )
  }

  // Standard login UI (no passkey hint or user clicked alternatives)
  return (
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
          isLoading={isLoading}
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
          isLoading={isLoading}
          error={error}
        />

        {/* Show passkey link for users who might have one */}
        {isWebAuthnSupported() && (
          <div className="text-center">
            <PasskeyLoginButton
              onSuccess={onPasskeySuccess}
              variant="link"
            />
          </div>
        )}
      </div>
    </>
  )
}

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
          <PasskeyFirstLogin
            onPasskeySuccess={(result) => {
              // Passkey auth returns real Stytch session tokens via sessions.attest()
              if (result.session_token && result.session_token !== PASSKEY_PLACEHOLDER_TOKEN) {
                // Set cookies that Stytch SDK will recognize
                // Example cookie attributes: domain=your-domain.com; path=/; secure; max-age=2592000 (30 days)
                const cookieOptions = "path=/; secure; max-age=2592000; SameSite=None"
                document.cookie = `stytch_session=${result.session_token}; ${cookieOptions}`
                document.cookie = `stytch_session_jwt=${result.session_jwt}; ${cookieOptions}`

                // Use full page redirect so Stytch SDK reinitializes with new session
                window.location.href = "/dashboard"
              } else {
                // Log error details without exposing sensitive data
                console.error("Passkey authentication failed", {
                  hasSessionToken: Boolean(result.session_token),
                  hasSessionJwt: Boolean(result.session_jwt),
                  hasValidToken: result.session_token && result.session_token !== PASSKEY_PLACEHOLDER_TOKEN,
                })
                toast.error("Authentication failed - no session received")
              }
            }}
            startGoogleOAuth={startGoogleOAuth}
            sendMagicLink={sendMagicLink}
            isLoading={state.isLoading}
            error={state.error}
          />
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
