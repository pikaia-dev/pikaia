import { StytchB2B, useStytchMemberSession } from "@stytch/react/b2b"
import {
  AuthFlowType,
  B2BOAuthProviders,
  B2BProducts,
} from "@stytch/vanilla-js/b2b"
import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

import { LoadingSpinner } from "../components/ui/loading-spinner"

// Session duration: 30 days
const SESSION_DURATION_MINUTES = 30 * 24 * 60

// Discovery config - let Stytch Dashboard handle redirect URLs
const stytchDiscoveryConfig = {
  products: [B2BProducts.emailMagicLinks, B2BProducts.oauth],
  sessionOptions: {
    sessionDurationMinutes: SESSION_DURATION_MINUTES,
  },
  authFlowType: AuthFlowType.Discovery,
  oauthOptions: {
    providers: [
      {
        type: B2BOAuthProviders.Google,
        customScopes: [
          "https://www.googleapis.com/auth/admin.directory.user.readonly",
        ],
      },
    ],
  },
  // Auto-login users who belong to exactly one organization
  directLoginForSingleMembership: {
    status: true,
    ignoreInvites: true, // Skip org picker even with pending invites
    ignoreJitProvisioning: true, // Skip org picker even with JIT-joinable orgs
  },
}

// Stytch styles aligned with shadcn/ui default theme (neutral/zinc)
const stytchStyles = {
  container: {
    width: "100%",
  },
  colors: {
    primary: "#18181b", // zinc-900 - matches shadcn primary
    secondary: "#71717a", // zinc-500 - muted text
    success: "#22c55e", // green-500
    error: "#ef4444", // red-500
  },
  buttons: {
    primary: {
      backgroundColor: "#18181b", // zinc-900
      textColor: "#fafafa", // zinc-50
      borderRadius: "6px", // matches shadcn radius
    },
  },
  inputs: {
    borderColor: "#e4e4e7", // zinc-200 - matches shadcn input border
    borderRadius: "6px",
  },
  fontFamily: "inherit", // Use app's font
}

export default function Login() {
  const navigate = useNavigate()
  const { session, isInitialized } = useStytchMemberSession()

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
        <div className="text-center mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">
            Welcome back
          </h1>
          <p className="text-sm text-muted-foreground mt-2">
            Sign in with Google or enter your email
          </p>
        </div>
        <StytchB2B config={stytchDiscoveryConfig} styles={stytchStyles} />
      </div>
    </div>
  )
}
