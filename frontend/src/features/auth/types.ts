import type { DiscoveredOrganization } from '@stytch/vanilla-js/b2b'

/**
 * Login flow steps for the custom login UI.
 */
export type LoginStep = 'email' | 'check-email' | 'select-org'

/**
 * Login state machine state.
 */
export interface LoginState {
  step: LoginStep
  email: string
  isLoading: boolean
  error: string | null
  discoveredOrganizations: DiscoveredOrganization[]
}

/**
 * Initial login state.
 */
export const initialLoginState: LoginState = {
  step: 'email',
  email: '',
  isLoading: false,
  error: null,
  discoveredOrganizations: [],
}
