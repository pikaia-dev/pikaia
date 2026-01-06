import { useStytchB2BClient } from "@stytch/react/b2b"
import type { DiscoveredOrganization } from "@stytch/vanilla-js/b2b"
import { useCallback, useState } from "react"

import { initialLoginState, type LoginState } from "./types"

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

/**
 * Determines if user should auto-login to a single organization.
 * Matches logic from directLoginForSingleMembership in StytchB2B component.
 */
function getSingleLoginOrg(
    organizations: DiscoveredOrganization[],
    options: DirectLoginOptions
): DiscoveredOrganization | null {
    if (!options.status) return null

    const activeMembers = organizations.filter(
        (org) => org.membership.type === "active_member"
    )

    // Check if there are any pending/invited/JIT orgs that would show the picker
    const hasPendingOrInvited = organizations.some((org) => {
        const type = org.membership.type
        if (
            (type === "pending_member" || type === "invited_member") &&
            !options.ignoreInvites
        ) {
            return true
        }
        if (type === "eligible_to_join_by_email_domain" && !options.ignoreJitProvisioning) {
            return true
        }
        return false
    })

    // Auto-login only if exactly one active member and no pending/invited/JIT orgs
    if (activeMembers.length === 1 && !hasPendingOrInvited) {
        return activeMembers[0]
    }

    return null
}

interface UseDiscoveryAuthReturn {
    state: LoginState
    sendMagicLink: (email: string) => Promise<void>
    startGoogleOAuth: () => void
    authenticateDiscoveryToken: (token: string) => Promise<void>
    authenticateOAuthToken: (token: string) => Promise<void>
    exchangeSession: (organizationId: string) => Promise<void>
    resetToEmail: () => void
    setError: (error: string | null) => void
    setDiscoveredOrganizations: (orgs: DiscoveredOrganization[]) => void
}

/**
 * Hook for managing Discovery auth flow with Stytch headless SDK.
 */
export function useDiscoveryAuth(): UseDiscoveryAuthReturn {
    const stytch = useStytchB2BClient()
    const [state, setState] = useState<LoginState>(initialLoginState)

    const setError = useCallback((error: string | null) => {
        setState((prev) => ({ ...prev, error, isLoading: false }))
    }, [])

    const setDiscoveredOrganizations = useCallback(
        (orgs: DiscoveredOrganization[]) => {
            setState((prev) => ({ ...prev, discoveredOrganizations: orgs }))
        },
        []
    )

    const resetToEmail = useCallback(() => {
        setState(initialLoginState)
    }, [])

    /**
     * Send a magic link email for Discovery flow.
     */
    const sendMagicLink = useCallback(
        async (email: string) => {
            setState((prev) => ({ ...prev, isLoading: true, error: null, email }))

            try {
                await stytch.magicLinks.email.discovery.send({
                    email_address: email,
                    discovery_redirect_url: `${window.location.origin}/auth/callback`,
                })

                setState((prev) => ({
                    ...prev,
                    isLoading: false,
                    step: "check-email",
                }))
            } catch (err) {
                const message =
                    err instanceof Error ? err.message : "Failed to send magic link"
                setState((prev) => ({
                    ...prev,
                    isLoading: false,
                    error: message,
                }))
            }
        },
        [stytch]
    )

    /**
     * Start Google OAuth Discovery flow.
     */
    const startGoogleOAuth = useCallback(() => {
        void stytch.oauth.google.discovery.start({
            discovery_redirect_url: `${window.location.origin}/auth/callback`,
            custom_scopes: [
                "https://www.googleapis.com/auth/admin.directory.user.readonly",
            ],
        })
    }, [stytch])

    /**
     * Authenticate discovery magic link token.
     */
    const authenticateDiscoveryToken = useCallback(
        async (token: string) => {
            setState((prev) => ({ ...prev, isLoading: true, error: null }))

            try {
                const response = await stytch.magicLinks.discovery.authenticate({
                    discovery_magic_links_token: token,
                })

                const orgs = response.discovered_organizations
                const autoLoginOrg = getSingleLoginOrg(orgs, directLoginOptions)

                if (autoLoginOrg) {
                    // Auto-login to single org
                    await stytch.discovery.intermediateSessions.exchange({
                        organization_id: autoLoginOrg.organization.organization_id,
                        session_duration_minutes: SESSION_DURATION_MINUTES,
                    })
                    // Session is set, navigation handled by caller
                } else {
                    // Show org selection
                    setState((prev) => ({
                        ...prev,
                        email: response.email_address,
                        discoveredOrganizations: orgs,
                        step: "select-org",
                        isLoading: false,
                    }))
                }
            } catch (err) {
                const message =
                    err instanceof Error ? err.message : "Authentication failed"
                setState((prev) => ({
                    ...prev,
                    isLoading: false,
                    error: message,
                }))
                throw err
            }
        },
        [stytch]
    )

    /**
     * Authenticate discovery OAuth token.
     */
    const authenticateOAuthToken = useCallback(
        async (token: string) => {
            setState((prev) => ({ ...prev, isLoading: true, error: null }))

            try {
                const response = await stytch.oauth.discovery.authenticate({
                    discovery_oauth_token: token,
                })

                const orgs = response.discovered_organizations
                const autoLoginOrg = getSingleLoginOrg(orgs, directLoginOptions)

                if (autoLoginOrg) {
                    // Auto-login to single org
                    await stytch.discovery.intermediateSessions.exchange({
                        organization_id: autoLoginOrg.organization.organization_id,
                        session_duration_minutes: SESSION_DURATION_MINUTES,
                    })
                    // Session is set, navigation handled by caller
                } else {
                    // Show org selection
                    setState((prev) => ({
                        ...prev,
                        email: response.email_address,
                        discoveredOrganizations: orgs,
                        step: "select-org",
                        isLoading: false,
                    }))
                }
            } catch (err) {
                const message =
                    err instanceof Error ? err.message : "Authentication failed"
                setState((prev) => ({
                    ...prev,
                    isLoading: false,
                    error: message,
                }))
                throw err
            }
        },
        [stytch]
    )

    /**
     * Exchange intermediate session for full session with an organization.
     */
    const exchangeSession = useCallback(
        async (organizationId: string) => {
            setState((prev) => ({ ...prev, isLoading: true, error: null }))

            try {
                await stytch.discovery.intermediateSessions.exchange({
                    organization_id: organizationId,
                    session_duration_minutes: SESSION_DURATION_MINUTES,
                })
                // Session is set, navigation handled by caller
            } catch (err) {
                const message =
                    err instanceof Error ? err.message : "Failed to join organization"
                setState((prev) => ({
                    ...prev,
                    isLoading: false,
                    error: message,
                }))
                throw err
            }
        },
        [stytch]
    )

    return {
        state,
        sendMagicLink,
        startGoogleOAuth,
        authenticateDiscoveryToken,
        authenticateOAuthToken,
        exchangeSession,
        resetToEmail,
        setError,
        setDiscoveredOrganizations,
    }
}
