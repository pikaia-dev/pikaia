import type { DiscoveredOrganization } from '@stytch/vanilla-js/b2b'

interface DirectLoginOptions {
  status: boolean
  ignoreInvites?: boolean
  ignoreJitProvisioning?: boolean
}

/**
 * Determines if user should auto-login to a single organization.
 * Returns the organization to auto-login to, or null if user should select.
 */
export function getSingleLoginOrg(
  organizations: DiscoveredOrganization[],
  options: DirectLoginOptions
): DiscoveredOrganization | null {
  if (!options.status) return null

  const activeMembers = organizations.filter((org) => org.membership.type === 'active_member')

  const hasPendingOrInvited = organizations.some((org) => {
    const type = org.membership.type
    if ((type === 'pending_member' || type === 'invited_member') && !options.ignoreInvites) {
      return true
    }
    if (type === 'eligible_to_join_by_email_domain' && !options.ignoreJitProvisioning) {
      return true
    }
    return false
  })

  if (activeMembers.length === 1 && !hasPendingOrInvited) {
    return activeMembers[0]
  }

  return null
}

export interface DerivedOrgInfo {
  orgName: string
  orgSlug: string
  baseName: string
  domainLabel: string
}

/**
 * Derives organization name and slug from an email address.
 * Handles edge cases where email format might be unexpected.
 */
export function deriveOrgFromEmail(email: string): DerivedOrgInfo {
  // Safely split email, handling missing @ or domain
  const atIndex = email.indexOf('@')
  const localPart = atIndex > 0 ? email.slice(0, atIndex) : email
  const domainPart = atIndex > 0 ? email.slice(atIndex + 1) : ''

  // Extract prefix from local part (max 8 alphanumeric chars)
  const emailPrefix = localPart.replace(/[^a-zA-Z0-9]/g, '').slice(0, 8) || 'user'

  // Extract domain label (part before first dot)
  const dotIndex = domainPart.indexOf('.')
  const domainLabel = dotIndex > 0 ? domainPart.slice(0, dotIndex) : domainPart || 'org'

  // Create readable name from domain (e.g., "my-company" -> "My Company")
  const baseName =
    domainLabel
      .split('-')
      .filter((word) => word.length > 0)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ') || 'Organization'

  // Make name unique by appending email prefix (e.g., "Gmail (johndoe)")
  const orgName = `${baseName} (${emailPrefix})`
  const orgSlug = `${domainLabel.toLowerCase()}-${emailPrefix.toLowerCase()}`

  return { orgName, orgSlug, baseName, domainLabel }
}

/**
 * Generates retry name and slug with timestamp for conflict resolution.
 */
export function generateRetryOrgInfo(
  baseName: string,
  domainLabel: string
): { retryName: string; retrySlug: string } {
  const timestamp = Date.now()
  const timestampSuffix = String(timestamp).slice(-6)
  const randomSuffix = Math.random().toString(36).slice(2, 8)
  const retryName = `${baseName} (${timestampSuffix})`
  const retrySlug = `${domainLabel.toLowerCase()}-${String(timestamp)}-${randomSuffix}`

  return { retryName, retrySlug }
}
