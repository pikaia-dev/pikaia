import type { DiscoveredOrganization } from '@stytch/vanilla-js/b2b'
import { describe, expect, it } from 'vitest'

import {
  deriveOrgFromEmail,
  generateRetryOrgInfo,
  getSingleLoginOrg,
} from '@/features/auth/utils/org-derivation'

// Helper to create mock discovered organizations
// Uses type assertion since Stytch types are complex with many required fields
function createMockOrg(id: string, membershipType: string): DiscoveredOrganization {
  return {
    organization: {
      organization_id: id,
      organization_name: `Org ${id}`,
      organization_slug: `org-${id}`,
    },
    membership: {
      type: membershipType,
    },
    member_authenticated: false,
  } as DiscoveredOrganization
}

describe('getSingleLoginOrg', () => {
  describe('when status is disabled', () => {
    it('returns null regardless of organizations', () => {
      const orgs = [createMockOrg('1', 'active_member')]
      const result = getSingleLoginOrg(orgs, { status: false })
      expect(result).toBeNull()
    })
  })

  describe('when status is enabled', () => {
    it('returns the org when there is exactly one active member', () => {
      const orgs = [createMockOrg('1', 'active_member')]
      const result = getSingleLoginOrg(orgs, { status: true })
      expect(result?.organization.organization_id).toBe('1')
    })

    it('returns null when there are no organizations', () => {
      const result = getSingleLoginOrg([], { status: true })
      expect(result).toBeNull()
    })

    it('returns null when there are multiple active members', () => {
      const orgs = [createMockOrg('1', 'active_member'), createMockOrg('2', 'active_member')]
      const result = getSingleLoginOrg(orgs, { status: true })
      expect(result).toBeNull()
    })

    it('returns null when there is a pending member and ignoreInvites is false', () => {
      const orgs = [createMockOrg('1', 'active_member'), createMockOrg('2', 'pending_member')]
      const result = getSingleLoginOrg(orgs, {
        status: true,
        ignoreInvites: false,
      })
      expect(result).toBeNull()
    })

    it('returns the active org when there is a pending member and ignoreInvites is true', () => {
      const orgs = [createMockOrg('1', 'active_member'), createMockOrg('2', 'pending_member')]
      const result = getSingleLoginOrg(orgs, {
        status: true,
        ignoreInvites: true,
      })
      expect(result?.organization.organization_id).toBe('1')
    })

    it('returns null when there is an invited member and ignoreInvites is false', () => {
      const orgs = [createMockOrg('1', 'active_member'), createMockOrg('2', 'invited_member')]
      const result = getSingleLoginOrg(orgs, {
        status: true,
        ignoreInvites: false,
      })
      expect(result).toBeNull()
    })

    it('returns the active org when there is an invited member and ignoreInvites is true', () => {
      const orgs = [createMockOrg('1', 'active_member'), createMockOrg('2', 'invited_member')]
      const result = getSingleLoginOrg(orgs, {
        status: true,
        ignoreInvites: true,
      })
      expect(result?.organization.organization_id).toBe('1')
    })

    it('returns null when eligible to join by email domain and ignoreJitProvisioning is false', () => {
      const orgs = [
        createMockOrg('1', 'active_member'),
        createMockOrg('2', 'eligible_to_join_by_email_domain'),
      ]
      const result = getSingleLoginOrg(orgs, {
        status: true,
        ignoreJitProvisioning: false,
      })
      expect(result).toBeNull()
    })

    it('returns the active org when eligible to join by email domain and ignoreJitProvisioning is true', () => {
      const orgs = [
        createMockOrg('1', 'active_member'),
        createMockOrg('2', 'eligible_to_join_by_email_domain'),
      ]
      const result = getSingleLoginOrg(orgs, {
        status: true,
        ignoreJitProvisioning: true,
      })
      expect(result?.organization.organization_id).toBe('1')
    })

    it('returns null when only pending members exist', () => {
      const orgs = [createMockOrg('1', 'pending_member')]
      const result = getSingleLoginOrg(orgs, { status: true })
      expect(result).toBeNull()
    })
  })
})

describe('deriveOrgFromEmail', () => {
  it('derives org info from a standard email', () => {
    const result = deriveOrgFromEmail('john.doe@company.com')

    expect(result.baseName).toBe('Company')
    expect(result.domainLabel).toBe('company')
    expect(result.orgName).toBe('Company (johndoe)')
    expect(result.orgSlug).toBe('company-johndoe')
  })

  it('handles email with hyphenated domain', () => {
    const result = deriveOrgFromEmail('user@my-awesome-company.io')

    expect(result.baseName).toBe('My Awesome Company')
    expect(result.domainLabel).toBe('my-awesome-company')
    expect(result.orgName).toBe('My Awesome Company (user)')
    expect(result.orgSlug).toBe('my-awesome-company-user')
  })

  it('handles gmail-style emails', () => {
    const result = deriveOrgFromEmail('testuser123@gmail.com')

    expect(result.baseName).toBe('Gmail')
    expect(result.domainLabel).toBe('gmail')
    expect(result.orgName).toBe('Gmail (testuser)')
    expect(result.orgSlug).toBe('gmail-testuser')
  })

  it('handles email with special characters in local part', () => {
    const result = deriveOrgFromEmail('john.doe+test@example.org')

    expect(result.baseName).toBe('Example')
    expect(result.orgName).toBe('Example (johndoet)')
    expect(result.orgSlug).toBe('example-johndoet')
  })

  it('truncates long email prefixes to 8 characters', () => {
    const result = deriveOrgFromEmail('verylongusername123456@domain.com')

    expect(result.orgName).toBe('Domain (verylong)')
    expect(result.orgSlug).toBe('domain-verylong')
  })

  it('handles email without @ symbol', () => {
    const result = deriveOrgFromEmail('invalid-email')

    // Without @, the whole string is treated as local part, domain falls back to "org"
    expect(result.baseName).toBe('Org')
    expect(result.domainLabel).toBe('org')
    expect(result.orgName).toBe('Org (invalide)')
    expect(result.orgSlug).toBe('org-invalide')
  })

  it('handles email with @ at position 0', () => {
    // When @ is at position 0, atIndex > 0 is false, so whole string is local part
    const result = deriveOrgFromEmail('@domain.com')

    expect(result.baseName).toBe('Org')
    expect(result.domainLabel).toBe('org')
    expect(result.orgName).toBe('Org (domainco)')
    expect(result.orgSlug).toBe('org-domainco')
  })

  it('handles email without domain extension', () => {
    const result = deriveOrgFromEmail('user@localhost')

    expect(result.baseName).toBe('Localhost')
    expect(result.domainLabel).toBe('localhost')
    expect(result.orgName).toBe('Localhost (user)')
    expect(result.orgSlug).toBe('localhost-user')
  })

  it('handles co.uk style domains', () => {
    const result = deriveOrgFromEmail('admin@company.co.uk')

    expect(result.baseName).toBe('Company')
    expect(result.domainLabel).toBe('company')
    expect(result.orgName).toBe('Company (admin)')
    expect(result.orgSlug).toBe('company-admin')
  })
})

describe('generateRetryOrgInfo', () => {
  it('generates retry info with timestamp suffix', () => {
    const result = generateRetryOrgInfo('Company', 'company')

    expect(result.retryName).toMatch(/^Company \(\d{6}\)$/)
    expect(result.retrySlug).toMatch(/^company-\d+-[a-z0-9]+$/)
  })

  it('generates unique slugs on each call', () => {
    const result1 = generateRetryOrgInfo('Test', 'test')
    const result2 = generateRetryOrgInfo('Test', 'test')

    // Random suffix should make them different
    expect(result1.retrySlug).not.toBe(result2.retrySlug)
  })

  it('lowercases domain label in slug', () => {
    const result = generateRetryOrgInfo('Company', 'COMPANY')

    expect(result.retrySlug).toMatch(/^company-/)
  })
})
