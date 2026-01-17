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
