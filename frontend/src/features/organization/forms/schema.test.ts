import { describe, expect, it } from 'vitest'

import { normalizeSlug, organizationSchema } from './schema'

describe('organizationSchema', () => {
  it('validates a correct organization', () => {
    const result = organizationSchema.safeParse({
      name: 'Acme Corp',
      slug: 'acme-corp',
    })
    expect(result.success).toBe(true)
  })

  it('rejects empty name', () => {
    const result = organizationSchema.safeParse({
      name: '',
      slug: 'acme-corp',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].path).toContain('name')
    }
  })

  it('rejects slug with invalid characters', () => {
    const result = organizationSchema.safeParse({
      name: 'Acme Corp',
      slug: 'acme corp!', // spaces and special chars
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].path).toContain('slug')
    }
  })

  it('rejects slug shorter than 2 characters', () => {
    const result = organizationSchema.safeParse({
      name: 'A',
      slug: 'a',
    })
    expect(result.success).toBe(false)
  })

  it('allows slug with allowed special characters', () => {
    const result = organizationSchema.safeParse({
      name: 'Test Org',
      slug: 'test.org_name~v2-beta',
    })
    expect(result.success).toBe(true)
  })
})

describe('normalizeSlug', () => {
  it('converts to lowercase', () => {
    expect(normalizeSlug('ACME')).toBe('acme')
  })

  it('replaces spaces with hyphens', () => {
    expect(normalizeSlug('acme corp')).toBe('acme-corp')
  })

  it('removes leading and trailing hyphens', () => {
    expect(normalizeSlug('-acme-')).toBe('acme')
  })

  it('replaces invalid characters with hyphens', () => {
    expect(normalizeSlug('acme@corp!')).toBe('acme-corp')
  })

  it('preserves allowed special characters', () => {
    expect(normalizeSlug('test.org_v2~beta')).toBe('test.org_v2~beta')
  })

  it('truncates to 128 characters', () => {
    const longSlug = 'a'.repeat(200)
    expect(normalizeSlug(longSlug).length).toBe(128)
  })

  it('trims whitespace', () => {
    expect(normalizeSlug('  acme  ')).toBe('acme')
  })
})
