/**
 * Stytch RBAC role identifiers.
 *
 * These must match the role IDs configured in the Stytch Dashboard.
 * @see https://stytch.com/docs/b2b/guides/rbac/overview
 */
export const STYTCH_ROLES = {
    /** Admin role ID - grants full organization management permissions */
    ADMIN: 'stytch_admin',
} as const
