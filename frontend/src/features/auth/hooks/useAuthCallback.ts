import { useStytchB2BClient } from "@stytch/react/b2b"
import type { DiscoveredOrganization } from "@stytch/vanilla-js/b2b"
import { useCallback, useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { directLoginOptions, SESSION_DURATION_MINUTES } from "../constants"
import { getErrorMessage } from "../utils"
import {
    createOrganization,
    isConflictError,
    type CreateOrgResponse,
} from "../utils/org-api"
import {
    deriveOrgFromEmail,
    generateRetryOrgInfo,
    getSingleLoginOrg,
} from "../utils/org-derivation"

export type TokenType =
    | "discovery"
    | "discovery_oauth"
    | "multi_tenant_magic_links"
    | "impersonation"
    | null

export interface AuthCallbackState {
    isLoading: boolean
    error: string | null
    showOrgSelector: boolean
    discoveredOrgs: DiscoveredOrganization[]
    email: string
    tokenType: TokenType
}

const initialState: AuthCallbackState = {
    isLoading: true,
    error: null,
    showOrgSelector: false,
    discoveredOrgs: [],
    email: "",
    tokenType: null,
}

export interface UseAuthCallbackOptions {
    onSuccess?: () => void
    onRedirectToLogin?: () => void
}

export interface UseAuthCallbackReturn {
    state: AuthCallbackState
    exchangeSession: (organizationId: string) => void
    goToLogin: () => void
}

/**
 * Hook for handling auth callback logic.
 * Processes Stytch tokens from URL and manages auth flow state.
 */
export function useAuthCallback(
    options: UseAuthCallbackOptions = {}
): UseAuthCallbackReturn {
    const stytch = useStytchB2BClient()
    const [searchParams] = useSearchParams()
    const [state, setState] = useState<AuthCallbackState>(initialState)
    const processedTokenRef = useRef(false)

    const setError = useCallback((error: string) => {
        setState((prev) => ({ ...prev, error, isLoading: false }))
    }, [])

    const setSuccess = useCallback(() => {
        sessionStorage.setItem("stytch_just_logged_in", "true")
        setState((prev) => ({ ...prev, error: null }))
        window.location.href = "/dashboard"
    }, [])

    const goToLogin = useCallback(() => {
        options.onRedirectToLogin?.()
    }, [options])

    /**
     * Exchange intermediate session for full session with an organization.
     */
    const exchangeSession = useCallback(
        (organizationId: string) => {
            setState((prev) => ({ ...prev, isLoading: true, error: null }))

            stytch.discovery.intermediateSessions
                .exchange({
                    organization_id: organizationId,
                    session_duration_minutes: SESSION_DURATION_MINUTES,
                })
                .catch((err: unknown) => {
                    setError(getErrorMessage(err, "Failed to join organization"))
                })
        },
        [stytch, setError]
    )

    /**
     * Creates organization with retry logic for name/slug conflicts.
     */
    const createOrganizationWithRetry = useCallback(
        async (
            intermediateSessionToken: string,
            email: string
        ): Promise<void> => {
            const { orgName, orgSlug, baseName, domainLabel } =
                deriveOrgFromEmail(email)

            const handleSuccess = (data: CreateOrgResponse): void => {
                stytch.session.updateSession({
                    session_token: data.session_token,
                    session_jwt: data.session_jwt,
                })
                setSuccess()
            }

            try {
                const data = await createOrganization(
                    intermediateSessionToken,
                    orgName,
                    orgSlug
                )
                handleSuccess(data)
            } catch (createErr: unknown) {
                if (isConflictError(createErr)) {
                    const { retryName, retrySlug } = generateRetryOrgInfo(
                        baseName,
                        domainLabel
                    )
                    const data = await createOrganization(
                        intermediateSessionToken,
                        retryName,
                        retrySlug
                    )
                    handleSuccess(data)
                } else {
                    throw createErr
                }
            }
        },
        [stytch, setSuccess]
    )

    /**
     * Processes discovered organizations after authentication.
     */
    const processDiscoveredOrgs = useCallback(
        async (
            orgs: DiscoveredOrganization[],
            email: string,
            intermediateSessionToken: string
        ): Promise<void> => {
            const autoLoginOrg = getSingleLoginOrg(orgs, directLoginOptions)

            if (autoLoginOrg) {
                sessionStorage.setItem("stytch_just_logged_in", "true")
                await stytch.discovery.intermediateSessions.exchange({
                    organization_id: autoLoginOrg.organization.organization_id,
                    session_duration_minutes: SESSION_DURATION_MINUTES,
                })
                window.location.href = "/dashboard"
            } else if (orgs.length === 0) {
                await createOrganizationWithRetry(intermediateSessionToken, email)
            } else {
                setState((prev) => ({
                    ...prev,
                    email,
                    discoveredOrgs: orgs,
                    showOrgSelector: true,
                    isLoading: false,
                }))
            }
        },
        [stytch, createOrganizationWithRetry]
    )

    /**
     * Handle discovery magic link token.
     */
    const handleDiscoveryToken = useCallback(
        async (token: string): Promise<void> => {
            const response = await stytch.magicLinks.discovery.authenticate({
                discovery_magic_links_token: token,
            })

            await processDiscoveredOrgs(
                response.discovered_organizations,
                response.email_address,
                response.intermediate_session_token
            )
        },
        [stytch, processDiscoveredOrgs]
    )

    /**
     * Handle OAuth discovery token.
     */
    const handleOAuthToken = useCallback(
        async (token: string): Promise<void> => {
            const response = await stytch.oauth.discovery.authenticate({
                discovery_oauth_token: token,
            })

            await processDiscoveredOrgs(
                response.discovered_organizations,
                response.email_address,
                response.intermediate_session_token
            )
        },
        [stytch, processDiscoveredOrgs]
    )

    /**
     * Handle org-scoped magic links (invites).
     */
    const handleInviteToken = useCallback(
        async (token: string): Promise<void> => {
            await stytch.magicLinks.authenticate({
                magic_links_token: token,
                session_duration_minutes: SESSION_DURATION_MINUTES,
            })
            setSuccess()
        },
        [stytch, setSuccess]
    )

    /**
     * Handle impersonation tokens from Stytch dashboard.
     */
    const handleImpersonationToken = useCallback(
        async (token: string): Promise<void> => {
            await stytch.impersonation.authenticate({
                impersonation_token: token,
            })
            setSuccess()
        },
        [stytch, setSuccess]
    )

    // Main effect to process token from URL
    useEffect(() => {
        if (processedTokenRef.current) return

        const tokenType = searchParams.get("stytch_token_type") as TokenType
        const token = searchParams.get("token")

        if (!token) {
            goToLogin()
            return
        }

        processedTokenRef.current = true
        setState((prev) => ({ ...prev, tokenType }))

        const processToken = async (): Promise<void> => {
            switch (tokenType) {
                case "discovery":
                    await handleDiscoveryToken(token)
                    break
                case "discovery_oauth":
                    await handleOAuthToken(token)
                    break
                case "multi_tenant_magic_links":
                    await handleInviteToken(token)
                    break
                case "impersonation":
                    await handleImpersonationToken(token)
                    break
                default:
                    goToLogin()
            }
        }

        processToken().catch((err: unknown) => {
            setError(getErrorMessage(err, "Authentication failed"))
        })
    }, [
        searchParams,
        goToLogin,
        handleDiscoveryToken,
        handleOAuthToken,
        handleInviteToken,
        handleImpersonationToken,
        setError,
    ])

    return {
        state,
        exchangeSession,
        goToLogin,
    }
}
