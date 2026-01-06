import { useStytchB2BClient, useStytchMemberSession } from "@stytch/react/b2b"
import type { DiscoveredOrganization } from "@stytch/vanilla-js/b2b"
import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { config } from "@/lib/env"

import { LoadingSpinner } from "../components/ui/loading-spinner"
import { OrganizationSelector } from "../features/auth/components"

// Session duration: 30 days
const SESSION_DURATION_MINUTES = 30 * 24 * 60

interface DirectLoginOptions {
  status: boolean
  ignoreInvites?: boolean
  ignoreJitProvisioning?: boolean
}

const directLoginOptions: DirectLoginOptions = {
  status: true,
  ignoreInvites: true,
  ignoreJitProvisioning: true,
}

/** API error response shape */
interface ApiErrorResponse {
  detail?: string
}

/**
 * Determines if user should auto-login to a single organization.
 */
function getSingleLoginOrg(
  organizations: DiscoveredOrganization[],
  options: DirectLoginOptions
): DiscoveredOrganization | null {
  if (!options.status) return null

  const activeMembers = organizations.filter(
    (org) => org.membership.type === "active_member"
  )

  const hasPendingOrInvited = organizations.some((org) => {
    const type = org.membership.type
    if (
      (type === "pending_member" || type === "invited_member") &&
      !options.ignoreInvites
    ) {
      return true
    }
    if (
      type === "eligible_to_join_by_email_domain" &&
      !options.ignoreJitProvisioning
    ) {
      return true
    }
    return false
  })

  if (activeMembers.length === 1 && !hasPendingOrInvited) {
    return activeMembers[0]
  }

  return null
}

/**
 * Auth callback handles Stytch redirects after magic link clicks and OAuth.
 */
export default function AuthCallback() {
  const stytch = useStytchB2BClient()
  const { session, isInitialized } = useStytchMemberSession()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [discoveredOrgs, setDiscoveredOrgs] = useState<
    DiscoveredOrganization[]
  >([])
  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showOrgSelector, setShowOrgSelector] = useState(false)

  const exchangeSession = useCallback(
    (organizationId: string) => {
      setIsLoading(true)
      setError(null)
      stytch.discovery.intermediateSessions
        .exchange({
          organization_id: organizationId,
          session_duration_minutes: SESSION_DURATION_MINUTES,
        })
        .catch((err: unknown) => {
          const message =
            err instanceof Error ? err.message : "Failed to join organization"
          setError(message)
          setIsLoading(false)
        })
      // Session is set, navigation handled by session effect
    },
    [stytch]
  )

  const goToLogin = useCallback(() => {
    // eslint-disable-next-line @typescript-eslint/no-floating-promises -- fire-and-forget navigation
    navigate("/login", { replace: true })
  }, [navigate])

  // Prevent double-invocation in React Strict Mode
  const processedTokenRef = useRef(false)

  useEffect(() => {
    if (processedTokenRef.current) return

    const tokenType = searchParams.get("stytch_token_type")
    const token = searchParams.get("token")

    // If no token, redirect to login
    if (!token) {
      // eslint-disable-next-line @typescript-eslint/no-floating-promises -- fire-and-forget navigation
      navigate("/login", { replace: true })
      return
    }

    processedTokenRef.current = true

    const handleDiscoveryToken = () => {
      stytch.magicLinks.discovery
        .authenticate({
          discovery_magic_links_token: token,
        })
        .then((response) => {
          const orgs = response.discovered_organizations
          const autoLoginOrg = getSingleLoginOrg(orgs, directLoginOptions)

          if (autoLoginOrg) {
            // Auto-login to single organization
            return stytch.discovery.intermediateSessions
              .exchange({
                organization_id: autoLoginOrg.organization.organization_id,
                session_duration_minutes: SESSION_DURATION_MINUTES,
              })
              .then(() => {
                // Success - Stytch session is set, navigation will happen via useEffect
                setError(null)
              })
          } else if (orgs.length === 0) {
            // Auto-create organization for new users
            const email = response.email_address
            const emailPrefix = email.split("@")[0].replace(/[^a-zA-Z0-9]/g, "").slice(0, 8)
            const domain = email.split("@")[1].split(".")[0]
            const baseName = domain
              .split("-")
              .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
              .join(" ")
            // Make name unique by appending email prefix (e.g., "Gmail (johndoe)")
            const orgName = `${baseName} (${emailPrefix})`
            const orgSlug = `${domain.toLowerCase()}-${emailPrefix.toLowerCase()}`

            // Call our backend API to create org and sync to database
            return fetch(`${config.apiUrl}/auth/discovery/create-org`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({
                intermediate_session_token: response.intermediate_session_token,
                organization_name: orgName,
                organization_slug: orgSlug,
              }),
            })
              .then(async (res) => {
                if (!res.ok) {
                  const errorBody = (await res
                    .json()
                    .catch(() => ({
                      detail: "Failed to create organization",
                    }))) as ApiErrorResponse
                  throw new Error(
                    errorBody.detail ?? "Failed to create organization"
                  )
                }
                return res.json() as Promise<{
                  session_token: string
                  session_jwt: string
                }>
              })
              .then((data) => {
                // Update Stytch SDK with new session
                stytch.session.updateSession({
                  session_token: data.session_token,
                  session_jwt: data.session_jwt,
                })
                // Full page reload to let SDK initialize with new session
                setError(null)
                // Set session flag to prevent login flash before redirect
                sessionStorage.setItem("stytch_just_logged_in", "true")
                void navigate("/dashboard", { replace: true })
              })
              .catch((createErr: unknown) => {
                // If name/slug conflict, retry with timestamp
                if (
                  createErr instanceof Error &&
                  (createErr.message.includes("slug") || createErr.message.includes("name") || createErr.message.includes("use"))
                ) {
                  const timestamp = Date.now()
                  const retryName = `${baseName} (${String(timestamp).slice(-6)})`
                  const retrySlug = `${domain.toLowerCase()}-${String(timestamp)}`
                  return fetch(`${config.apiUrl}/auth/discovery/create-org`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify({
                      intermediate_session_token:
                        response.intermediate_session_token,
                      organization_name: retryName,
                      organization_slug: retrySlug,
                    }),
                  })
                    .then(async (res) => {
                      if (!res.ok) {
                        const errorBody = (await res
                          .json()
                          .catch(() => ({
                            detail: "Failed to create organization",
                          }))) as ApiErrorResponse
                        throw new Error(
                          errorBody.detail ?? "Failed to create organization"
                        )
                      }
                      return res.json() as Promise<{
                        session_token: string
                        session_jwt: string
                      }>
                    })
                    .then((data) => {
                      stytch.session.updateSession({
                        session_token: data.session_token,
                        session_jwt: data.session_jwt,
                      })
                      setError(null)
                      // Set session flag to prevent login flash before redirect
                      sessionStorage.setItem("stytch_just_logged_in", "true")
                      void navigate("/dashboard", { replace: true })
                    })
                }
                console.error("❌ Failed to create organization:", createErr)
                throw createErr
              })
          } else {
            // Multiple organizations - show selector
            setEmail(response.email_address)
            setDiscoveredOrgs(orgs)
            setShowOrgSelector(true)
            setIsLoading(false)
            return undefined
          }
        })
        .catch((err: unknown) => {
          const message =
            err instanceof Error ? err.message : "Authentication failed"
          setError(message)
          setIsLoading(false)
        })
    }

    const handleOAuthToken = () => {
      stytch.oauth.discovery
        .authenticate({
          discovery_oauth_token: token,
        })
        .then((response) => {
          const orgs = response.discovered_organizations
          const autoLoginOrg = getSingleLoginOrg(orgs, directLoginOptions)

          if (autoLoginOrg) {
            // Auto-login to single organization
            void stytch.discovery.intermediateSessions.exchange({
              organization_id: autoLoginOrg.organization.organization_id,
              session_duration_minutes: SESSION_DURATION_MINUTES,
            })
            return
          } else if (orgs.length === 0) {
            // Auto-create organization for new users
            const email = response.email_address
            const emailPrefix = email.split("@")[0].replace(/[^a-zA-Z0-9]/g, "").slice(0, 8)
            const domain = email.split("@")[1].split(".")[0]
            const baseName = domain
              .split("-")
              .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
              .join(" ")
            // Make name unique by appending email prefix (e.g., "Gmail (johndoe)")
            const orgName = `${baseName} (${emailPrefix})`
            const orgSlug = `${domain.toLowerCase()}-${emailPrefix.toLowerCase()}`

            // Call our backend API to create org and sync to database
            return fetch(`${config.apiUrl}/auth/discovery/create-org`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({
                intermediate_session_token: response.intermediate_session_token,
                organization_name: orgName,
                organization_slug: orgSlug,
              }),
            })
              .then(async (res) => {
                if (!res.ok) {
                  const errorBody = (await res
                    .json()
                    .catch(() => ({
                      detail: "Failed to create organization",
                    }))) as ApiErrorResponse
                  throw new Error(
                    errorBody.detail ?? "Failed to create organization"
                  )
                }
                return res.json() as Promise<{
                  session_token: string
                  session_jwt: string
                }>
              })
              .then((data) => {
                stytch.session.updateSession({
                  session_token: data.session_token,
                  session_jwt: data.session_jwt,
                })
                setError(null)
                // Set session flag to prevent login flash before redirect
                sessionStorage.setItem("stytch_just_logged_in", "true")
                void navigate("/dashboard", { replace: true })
              })
              .catch((createErr: unknown) => {
                // If name/slug conflict, retry with timestamp
                if (
                  createErr instanceof Error &&
                  (createErr.message.includes("slug") || createErr.message.includes("name") || createErr.message.includes("use"))
                ) {
                  const timestamp = Date.now()
                  const retryName = `${baseName} (${String(timestamp).slice(-6)})`
                  const retrySlug = `${domain.toLowerCase()}-${String(timestamp)}`
                  return fetch(`${config.apiUrl}/auth/discovery/create-org`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify({
                      intermediate_session_token:
                        response.intermediate_session_token,
                      organization_name: retryName,
                      organization_slug: retrySlug,
                    }),
                  })
                    .then(async (res) => {
                      if (!res.ok) {
                        const errorBody = (await res
                          .json()
                          .catch(() => ({
                            detail: "Failed to create organization",
                          }))) as ApiErrorResponse
                        throw new Error(
                          errorBody.detail ?? "Failed to create organization"
                        )
                      }
                      return res.json() as Promise<{
                        session_token: string
                        session_jwt: string
                      }>
                    })
                    .then((data) => {
                      stytch.session.updateSession({
                        session_token: data.session_token,
                        session_jwt: data.session_jwt,
                      })
                      setError(null)
                      // Set session flag to prevent login flash before redirect
                      sessionStorage.setItem("stytch_just_logged_in", "true")
                      void navigate("/dashboard", { replace: true })
                    })
                }
                console.error("❌ Failed to create organization:", createErr)
                throw createErr
              })
          } else {
            // Multiple organizations - show selector
            setEmail(response.email_address)
            setDiscoveredOrgs(orgs)
            setShowOrgSelector(true)
            setIsLoading(false)
            return undefined
          }
        })
        .catch((err: unknown) => {
          const message =
            err instanceof Error ? err.message : "Authentication failed"
          setError(message)
          setIsLoading(false)
        })
    }

    if (
      tokenType === "discovery" ||
      tokenType === "multi_tenant_magic_links"
    ) {
      handleDiscoveryToken()
    } else if (tokenType === "discovery_oauth") {
      handleOAuthToken()
    } else {
      // Unknown token type, redirect to login
      // eslint-disable-next-line @typescript-eslint/no-floating-promises -- fire-and-forget navigation
      navigate("/login", { replace: true })
    }
  }, [searchParams, stytch, navigate])

  // Redirect to dashboard when session is established
  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized can be false during SDK init
    if (isInitialized && session) {
      void navigate("/dashboard", { replace: true })
    }
  }, [session, isInitialized, navigate])

  // Show org selector for multi-org users
  if (showOrgSelector) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="w-full max-w-sm p-8">
          <OrganizationSelector
            organizations={discoveredOrgs}
            onSelect={exchangeSession}
            onBack={goToLogin}
            isLoading={isLoading}
            error={error}
            email={email}
          />
        </div>
      </div>
    )
  }

  // Show error state
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <p className="text-destructive mb-4">{error}</p>
          <button
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
