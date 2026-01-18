import { describe, expect, it } from 'vitest'

import { billingAddressSchema, invoiceDeliverySchema } from './schema'

describe('invoiceDeliverySchema', () => {
  it('validates when billing email is not used', () => {
    const result = invoiceDeliverySchema.safeParse({
      use_billing_email: false,
    })
    expect(result.success).toBe(true)
  })

  it('validates when billing email is used with valid email', () => {
    const result = invoiceDeliverySchema.safeParse({
      use_billing_email: true,
      billing_email: 'billing@company.com',
    })
    expect(result.success).toBe(true)
  })

  it('rejects when billing email is used but email is missing', () => {
    const result = invoiceDeliverySchema.safeParse({
      use_billing_email: true,
    })
    expect(result.success).toBe(false)
  })

  it('rejects when billing email is used but email is invalid', () => {
    const result = invoiceDeliverySchema.safeParse({
      use_billing_email: true,
      billing_email: 'not-an-email',
    })
    expect(result.success).toBe(false)
  })

  it('allows empty billing_email when not using billing email', () => {
    const result = invoiceDeliverySchema.safeParse({
      use_billing_email: false,
      billing_email: '',
    })
    expect(result.success).toBe(true)
  })
})

describe('billingAddressSchema', () => {
  it('validates an empty address (all fields optional)', () => {
    const result = billingAddressSchema.safeParse({})
    expect(result.success).toBe(true)
  })

  it('validates a complete address', () => {
    const result = billingAddressSchema.safeParse({
      billing_name: 'Acme Corp',
      line1: '123 Main St',
      line2: 'Suite 100',
      city: 'San Francisco',
      state: 'CA',
      postal_code: '94105',
      country: 'US',
      vat_id: 'DE123456789',
    })
    expect(result.success).toBe(true)
  })

  it('rejects invalid country code (not 2 chars)', () => {
    const result = billingAddressSchema.safeParse({
      country: 'USA',
    })
    expect(result.success).toBe(false)
  })

  it('rejects too long billing name', () => {
    const result = billingAddressSchema.safeParse({
      billing_name: 'a'.repeat(256),
    })
    expect(result.success).toBe(false)
  })

  it('rejects too long VAT ID', () => {
    const result = billingAddressSchema.safeParse({
      vat_id: 'a'.repeat(51),
    })
    expect(result.success).toBe(false)
  })
})
