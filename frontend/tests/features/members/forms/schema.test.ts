import { describe, expect, it } from 'vitest'

import { inviteMemberSchema } from '@/features/members/forms/schema'

describe('inviteMemberSchema', () => {
  it('validates a correct invitation', () => {
    const result = inviteMemberSchema.safeParse({
      email: 'user@example.com',
      name: 'Jane Doe',
      role: 'member',
    })
    expect(result.success).toBe(true)
  })

  it('validates invitation without optional name', () => {
    const result = inviteMemberSchema.safeParse({
      email: 'user@example.com',
      role: 'admin',
    })
    expect(result.success).toBe(true)
  })

  it('rejects invalid email', () => {
    const result = inviteMemberSchema.safeParse({
      email: 'not-an-email',
      role: 'member',
    })
    expect(result.success).toBe(false)
  })

  it('rejects invalid role', () => {
    const result = inviteMemberSchema.safeParse({
      email: 'user@example.com',
      role: 'superadmin',
    })
    expect(result.success).toBe(false)
  })

  it('accepts admin role', () => {
    const result = inviteMemberSchema.safeParse({
      email: 'user@example.com',
      role: 'admin',
    })
    expect(result.success).toBe(true)
  })

  it('accepts member role', () => {
    const result = inviteMemberSchema.safeParse({
      email: 'user@example.com',
      role: 'member',
    })
    expect(result.success).toBe(true)
  })
})
