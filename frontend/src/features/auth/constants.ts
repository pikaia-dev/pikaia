/**
 * Session duration in minutes (30 days).
 */
export const SESSION_DURATION_MINUTES = 30 * 24 * 60

/**
 * Options for auto-login to single organization.
 * - ignoreInvites: Don't show org picker for pending/invited memberships
 * - ignoreJitProvisioning: Don't show org picker for JIT-eligible domains
 */
export const directLoginOptions = {
  status: true,
  ignoreInvites: true,
  ignoreJitProvisioning: true,
} as const

export type DirectLoginOptions = typeof directLoginOptions

/**
 * SessionStorage and localStorage keys used across the auth flow.
 *
 * Centralized here to avoid magic strings scattered across components.
 */
export const AUTH_STORAGE_KEYS = {
  /** Flags that user just logged in so ProtectedRoute waits for the Stytch session to propagate. */
  JUST_LOGGED_IN: 'stytch_just_logged_in',
  /** Flags that the current OAuth callback originated from the "connect provider" settings flow. */
  OAUTH_CONNECT_FLOW: 'oauth_connect_flow',
  /** Flags that a provider was just connected so the settings page can show a success toast after redirect. */
  PROVIDER_JUST_CONNECTED: 'provider_just_connected',
  /** Remembers that the user has previously authenticated with a passkey (localStorage). */
  PASSKEY_HINT: 'passkey_hint',
  /** Tracks whether the passkey enrollment prompt was dismissed this session (sessionStorage). */
  PASSKEY_PROMPT_DISMISSED: 'passkey_prompt_dismissed',
  /** Persists the user's choice to never see the passkey enrollment prompt again (localStorage). */
  PASSKEY_PROMPT_NEVER_ASK: 'passkey_prompt_never_ask',
} as const
