import { useStytchMemberSession } from "@stytch/react/b2b"
import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

import { LoadingSpinner } from "../components/ui/loading-spinner"

/**
 * Auth callback redirects to login page where StytchB2B handles everything.
 */
export default function AuthCallback() {
  const { session, isInitialized } = useStytchMemberSession()
  const navigate = useNavigate()

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized can be false
    if (!isInitialized) return

    if (session) {
      // eslint-disable-next-line @typescript-eslint/no-floating-promises -- navigate returns void
      navigate("/dashboard", { replace: true })
    } else {
      const currentUrl = new URL(window.location.href)
      // eslint-disable-next-line @typescript-eslint/no-floating-promises -- navigate returns void
      navigate(`/login${currentUrl.search}`, { replace: true })
    }
  }, [session, isInitialized, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <LoadingSpinner className="mx-auto" />
        <p className="mt-4 text-sm text-muted-foreground">Redirecting...</p>
      </div>
    </div>
  )
}
