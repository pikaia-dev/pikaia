import { useStytchB2BClient } from '@stytch/react/b2b'
import type { DiscoveredOrganization } from '@stytch/vanilla-js/b2b'
import { useCallback, useState } from 'react'

import { directLoginOptions, SESSION_DURATION_MINUTES } from '@/features/auth/constants'
import { initialLoginState, type LoginState } from '@/features/auth/types'
import { getErrorMessage } from '@/features/auth/utils/error-helpers'
import { getSingleLoginOrg } from '@/features/auth/utils/org-derivation'

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

  const setDiscoveredOrganizations = useCallback((orgs: DiscoveredOrganization[]) => {
    setState((prev) => ({ ...prev, discoveredOrganizations: orgs }))
  }, [])

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
          step: 'check-email',
        }))
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: getErrorMessage(err, 'Failed to send magic link'),
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
      custom_scopes: ['https://www.googleapis.com/auth/admin.directory.user.readonly'],
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
          await stytch.discovery.intermediateSessions.exchange({
            organization_id: autoLoginOrg.organization.organization_id,
            session_duration_minutes: SESSION_DURATION_MINUTES,
          })
        } else {
          setState((prev) => ({
            ...prev,
            email: response.email_address,
            discoveredOrganizations: orgs,
            step: 'select-org',
            isLoading: false,
          }))
        }
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: getErrorMessage(err, 'Authentication failed'),
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
          await stytch.discovery.intermediateSessions.exchange({
            organization_id: autoLoginOrg.organization.organization_id,
            session_duration_minutes: SESSION_DURATION_MINUTES,
          })
        } else {
          setState((prev) => ({
            ...prev,
            email: response.email_address,
            discoveredOrganizations: orgs,
            step: 'select-org',
            isLoading: false,
          }))
        }
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: getErrorMessage(err, 'Authentication failed'),
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
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: getErrorMessage(err, 'Failed to join organization'),
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
