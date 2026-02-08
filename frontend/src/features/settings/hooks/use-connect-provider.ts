import { useStytchB2BClient, useStytchMember } from '@stytch/react/b2b'
import { useCallback } from 'react'

const OAUTH_CONNECT_FLOW_KEY = 'oauth_connect_flow'

/**
 * Hook for connecting OAuth providers from settings page.
 *
 * Uses org-scoped OAuth (not discovery) since user is already authenticated.
 * Sets a sessionStorage flag so the auth callback knows to redirect back
 * to settings instead of the dashboard.
 */
export function useConnectProvider() {
  const stytch = useStytchB2BClient()
  const { member } = useStytchMember()

  const connectGoogle = useCallback(() => {
    if (!member?.organization_id) return
    sessionStorage.setItem(OAUTH_CONNECT_FLOW_KEY, 'true')
    void stytch.oauth.google.start({
      organization_id: member.organization_id,
      login_redirect_url: `${window.location.origin}/auth/callback`,
      signup_redirect_url: `${window.location.origin}/auth/callback`,
      custom_scopes: ['https://www.googleapis.com/auth/admin.directory.user.readonly'],
    })
  }, [stytch, member?.organization_id])

  const connectGitHub = useCallback(() => {
    if (!member?.organization_id) return
    sessionStorage.setItem(OAUTH_CONNECT_FLOW_KEY, 'true')
    void stytch.oauth.github.start({
      organization_id: member.organization_id,
      login_redirect_url: `${window.location.origin}/auth/callback`,
      signup_redirect_url: `${window.location.origin}/auth/callback`,
    })
  }, [stytch, member?.organization_id])

  return { connectGoogle, connectGitHub }
}

/**
 * Check if current auth callback is a connect flow (not a login).
 */
export function isConnectFlow(): boolean {
  return sessionStorage.getItem(OAUTH_CONNECT_FLOW_KEY) === 'true'
}

/**
 * Clear the connect flow flag after handling.
 */
export function clearConnectFlow(): void {
  sessionStorage.removeItem(OAUTH_CONNECT_FLOW_KEY)
}
