import { describe, expect, it } from 'vitest'

import {
  detectColumnType,
  detectHasHeader,
  normalizePhone,
  normalizeRole,
  parseCsvData,
  parseRowsWithMappings,
} from '@/features/members/utils/csv-import'

describe('detectHasHeader', () => {
  it('detects header row with email keyword', () => {
    expect(detectHasHeader(['Name', 'Email', 'Phone'])).toBe(true)
  })

  it('detects header row with various keywords', () => {
    expect(detectHasHeader(['full_name', 'e-mail', 'mobile'])).toBe(true)
    expect(detectHasHeader(['Name', 'Role', 'Type'])).toBe(true)
  })

  it('returns false when first row contains email addresses', () => {
    expect(detectHasHeader(['John', 'john@example.com', '123456789'])).toBe(false)
  })

  it('returns false when row has no header keywords', () => {
    expect(detectHasHeader(['John', 'Doe', '123456789'])).toBe(false)
  })

  it('returns false for data row even with text', () => {
    // "wojtek" looks like text but wojtek+11@tango.agency is an email
    expect(detectHasHeader(['wojtek', 'wojtek+11@tango.agency', '728340556'])).toBe(false)
  })

  it('handles empty row', () => {
    expect(detectHasHeader([])).toBe(false)
  })
})

describe('detectColumnType', () => {
  describe('header-based detection', () => {
    it('detects email from header', () => {
      expect(detectColumnType('Email', [])).toBe('email')
      expect(detectColumnType('E-mail', [])).toBe('email')
      expect(detectColumnType('email_address', [])).toBe('email')
    })

    it('detects name from header', () => {
      expect(detectColumnType('Name', [])).toBe('name')
      expect(detectColumnType('Full Name', [])).toBe('name')
      expect(detectColumnType('full_name', [])).toBe('name')
      expect(detectColumnType('fullname', [])).toBe('name')
    })

    it('detects phone from header', () => {
      expect(detectColumnType('Phone', [])).toBe('phone')
      expect(detectColumnType('Mobile', [])).toBe('phone')
      expect(detectColumnType('telephone', [])).toBe('phone')
    })

    it('detects role from header', () => {
      expect(detectColumnType('Role', [])).toBe('role')
      expect(detectColumnType('Type', [])).toBe('role')
      expect(detectColumnType('Permission', [])).toBe('role')
    })
  })

  describe('content-based detection', () => {
    it('detects email from @ symbol in samples', () => {
      const samples = ['john@example.com', 'jane@test.org', 'bob@company.co']
      expect(detectColumnType('Column 1', samples)).toBe('email')
    })

    it('detects phone from numeric samples', () => {
      const samples = ['+14155551234', '14155559999', '+48728340556']
      expect(detectColumnType('Column 2', samples)).toBe('phone')
    })

    it('detects phone with various formats', () => {
      const samples = ['(415) 555-1234', '+1-415-555-9999', '48 728 340 556']
      expect(detectColumnType('Column 2', samples)).toBe('phone')
    })

    it('detects role from role-like values', () => {
      const samples = ['admin', 'member', 'admin']
      expect(detectColumnType('Column 3', samples)).toBe('role')
    })

    it('detects name from text-only samples', () => {
      const samples = ['John Doe', 'Jane Smith', "Bob O'Brien"]
      expect(detectColumnType('Column 1', samples)).toBe('name')
    })

    it('returns skip for empty samples', () => {
      expect(detectColumnType('Column 1', [])).toBe('skip')
      expect(detectColumnType('Column 1', ['', '  ', ''])).toBe('skip')
    })

    it('returns skip for mixed/unrecognized content', () => {
      const samples = ['abc123', 'def456', 'ghi789']
      expect(detectColumnType('Column 1', samples)).toBe('skip')
    })

    it('detects email even with some invalid emails (threshold-based)', () => {
      // 3 out of 4 are valid emails (75%) - should detect as email
      const samples = ['john@example.com', 'jane@test.org', 'invalid-email', 'bob@company.co']
      expect(detectColumnType('Column 1', samples)).toBe('email')
    })

    it('detects phone even with some invalid phones (threshold-based)', () => {
      // 3 out of 4 are valid phones (75%) - should detect as phone
      const samples = ['+14155551234', '14155559999', 'abc', '+48728340556']
      expect(detectColumnType('Column 2', samples)).toBe('phone')
    })

    it('detects role even with some non-role values (threshold-based)', () => {
      // 2 out of 3 are valid roles (67%) - should detect as role
      const samples = ['admin', 'member', 'unknown-value']
      expect(detectColumnType('Column 3', samples)).toBe('role')
    })
  })
})

describe('parseCsvData', () => {
  it('parses CSV with header row', () => {
    const data = [
      ['Name', 'Email', 'Phone', 'Role'],
      ['John', 'john@example.com', '+14155551234', 'admin'],
      ['Jane', 'jane@example.com', '+14155559999', 'member'],
    ]

    const result = parseCsvData(data)

    expect(result.hasHeader).toBe(true)
    expect(result.headers).toEqual(['Name', 'Email', 'Phone', 'Role'])
    expect(result.rows).toHaveLength(2)
    expect(result.columnMappings[0]).toBe('name')
    expect(result.columnMappings[1]).toBe('email')
    expect(result.columnMappings[2]).toBe('phone')
    expect(result.columnMappings[3]).toBe('role')
  })

  it('parses CSV without header row', () => {
    const data = [
      ['John', 'john@example.com', '+14155551234', 'admin'],
      ['Jane', 'jane@example.com', '+14155559999', 'member'],
    ]

    const result = parseCsvData(data)

    expect(result.hasHeader).toBe(false)
    expect(result.headers).toEqual(['Column 1', 'Column 2', 'Column 3', 'Column 4'])
    expect(result.rows).toHaveLength(2)
    // Auto-detection from content
    expect(result.columnMappings[1]).toBe('email')
    expect(result.columnMappings[2]).toBe('phone')
    expect(result.columnMappings[3]).toBe('role')
  })

  it('handles single row without header', () => {
    const data = [['wojtek', 'wojtek+11@tango.agency', '728340556', 'member']]

    const result = parseCsvData(data)

    expect(result.hasHeader).toBe(false)
    expect(result.rows).toHaveLength(1)
    expect(result.columnMappings[1]).toBe('email')
    expect(result.columnMappings[2]).toBe('phone')
    expect(result.columnMappings[3]).toBe('role')
  })

  it('handles empty data', () => {
    const result = parseCsvData([])

    expect(result.headers).toEqual([])
    expect(result.rows).toEqual([])
    expect(result.columnMappings).toEqual({})
  })

  it('generates column names for missing headers', () => {
    const data = [
      ['', 'Email', ''],
      ['John', 'john@example.com', '+14155551234'],
    ]

    const result = parseCsvData(data)

    expect(result.headers[0]).toBe('Column 1')
    expect(result.headers[1]).toBe('Email')
    expect(result.headers[2]).toBe('Column 3')
  })
})

describe('normalizePhone', () => {
  it('keeps + prefix if present', () => {
    expect(normalizePhone('+14155551234')).toBe('+14155551234')
  })

  it('removes spaces, dashes, and parentheses', () => {
    expect(normalizePhone('+1 415 555 1234')).toBe('+14155551234')
    expect(normalizePhone('+1-415-555-1234')).toBe('+14155551234')
  })

  it('returns empty for invalid phone', () => {
    expect(normalizePhone('abc')).toBe('')
    expect(normalizePhone('123')).toBe('') // Too short
    expect(normalizePhone('')).toBe('')
  })

  it('handles Polish phone numbers with +', () => {
    expect(normalizePhone('+48728340556')).toBe('+48728340556')
  })

  it('handles 00 international prefix', () => {
    expect(normalizePhone('0048728340556')).toBe('+48728340556')
    expect(normalizePhone('001415555123')).toBe('+1415555123')
  })

  it('applies assumed dial code when no country code present', () => {
    expect(normalizePhone('728340556', '+48')).toBe('+48728340556')
    expect(normalizePhone('4155551234', '+1')).toBe('+14155551234')
  })

  it('does not apply assumed dial code when already has country code', () => {
    expect(normalizePhone('+48728340556', '+1')).toBe('+48728340556')
    expect(normalizePhone('0048728340556', '+1')).toBe('+48728340556')
  })
})

describe('normalizeRole', () => {
  it('normalizes admin roles', () => {
    expect(normalizeRole('admin')).toBe('admin')
    expect(normalizeRole('Admin')).toBe('admin')
    expect(normalizeRole('ADMIN')).toBe('admin')
    expect(normalizeRole('administrator')).toBe('admin')
  })

  it('normalizes member roles', () => {
    expect(normalizeRole('member')).toBe('member')
    expect(normalizeRole('Member')).toBe('member')
    expect(normalizeRole('user')).toBe('member')
  })

  it('defaults to member for empty or unknown', () => {
    expect(normalizeRole('')).toBe('member')
    expect(normalizeRole('   ')).toBe('member')
    expect(normalizeRole('unknown')).toBe('member')
    expect(normalizeRole('viewer')).toBe('member')
  })
})

describe('parseRowsWithMappings', () => {
  it('parses rows with all columns mapped', () => {
    const rows = [
      ['john@example.com', 'John Doe', '+14155551234', 'admin'],
      ['jane@example.com', 'Jane Smith', '+14155559999', 'member'],
    ]
    const mappings = {
      0: 'email' as const,
      1: 'name' as const,
      2: 'phone' as const,
      3: 'role' as const,
    }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result).toHaveLength(2)
    expect(result[0]).toEqual({
      email: 'john@example.com',
      name: 'John Doe',
      phone: '+14155551234',
      rawPhone: '+14155551234',
      phoneAssumed: false,
      role: 'admin',
      errors: [],
    })
    expect(result[1]).toEqual({
      email: 'jane@example.com',
      name: 'Jane Smith',
      phone: '+14155559999',
      rawPhone: '+14155559999',
      phoneAssumed: false,
      role: 'member',
      errors: [],
    })
  })

  it('handles email-only mapping', () => {
    const rows = [['john@example.com', 'ignored', 'ignored']]
    const mappings = { 0: 'email' as const, 1: 'skip' as const, 2: 'skip' as const }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result[0].email).toBe('john@example.com')
    expect(result[0].name).toBe('')
    expect(result[0].phone).toBe('')
    expect(result[0].role).toBe('member') // Default
    expect(result[0].errors).toEqual([])
  })

  it('validates missing email', () => {
    const rows = [['', 'John', '+14155551234']]
    const mappings = { 0: 'email' as const, 1: 'name' as const, 2: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result[0].errors).toContain('Email is required')
  })

  it('validates invalid email format', () => {
    const rows = [['not-an-email', 'John', '+14155551234']]
    const mappings = { 0: 'email' as const, 1: 'name' as const, 2: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result[0].errors).toContain('Invalid email format')
  })

  it('validates invalid phone format', () => {
    const rows = [['john@example.com', 'John', 'abc']]
    const mappings = { 0: 'email' as const, 1: 'name' as const, 2: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result[0].errors).toContain('Invalid phone format')
    expect(result[0].phone).toBe('') // Cleared invalid phone
  })

  it('normalizes email to lowercase', () => {
    const rows = [['JOHN@EXAMPLE.COM', 'John', '']]
    const mappings = { 0: 'email' as const, 1: 'name' as const }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result[0].email).toBe('john@example.com')
  })

  it('defaults role to member when not mapped', () => {
    const rows = [['john@example.com', 'John']]
    const mappings = { 0: 'email' as const, 1: 'name' as const }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result[0].role).toBe('member')
  })

  it('handles real-world CSV data with assumed country code', () => {
    // User's actual test case - Polish number without country code
    const rows = [['wojtek', 'wojtek+11@tango.agency', '728340556', ' member']]
    const mappings = {
      0: 'name' as const,
      1: 'email' as const,
      2: 'phone' as const,
      3: 'role' as const,
    }

    const result = parseRowsWithMappings(rows, mappings, '+48')

    expect(result[0]).toEqual({
      email: 'wojtek+11@tango.agency',
      name: 'wojtek',
      phone: '+48728340556',
      rawPhone: '728340556',
      phoneAssumed: true,
      role: 'member',
      errors: [],
    })
  })

  it('does not apply assumed code when phone already has country code', () => {
    const rows = [['john@example.com', '+48728340556']]
    const mappings = { 0: 'email' as const, 1: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings, '+1') // Trying to assume US

    expect(result[0].phone).toBe('+48728340556') // Keeps Polish code
    expect(result[0].phoneAssumed).toBe(false)
  })

  it('handles 0048 international format', () => {
    const rows = [['john@example.com', '0048728340556']]
    const mappings = { 0: 'email' as const, 1: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings)

    expect(result[0].phone).toBe('+48728340556')
    expect(result[0].phoneAssumed).toBe(false)
  })

  it('validates US phone numbers must be 10 digits when US assumed', () => {
    const rows = [
      ['valid@example.com', '5551234567'], // Valid: 10 digits
      ['short@example.com', '123456789'], // Invalid: 9 digits
      ['long@example.com', '123456789012'], // Invalid: 12 digits
      ['formatted@example.com', '(555) 123-4567'], // Valid: 10 digits with formatting
      ['with1@example.com', '1-(555)-123-4567'], // Valid: 11 digits with leading 1 (NANP format)
    ]
    const mappings = { 0: 'email' as const, 1: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings, '+1')

    expect(result[0].errors).toEqual([])
    expect(result[0].phone).toBe('+15551234567')

    expect(result[1].errors).toContain('US phone must be 10 digits')

    expect(result[2].errors).toContain('US phone must be 10 digits')

    expect(result[3].errors).toEqual([])
    expect(result[3].phone).toBe('+15551234567')

    // 1-555-123-4567 is recognized as already having US country code
    expect(result[4].errors).toEqual([])
    expect(result[4].phone).toBe('+15551234567')
    expect(result[4].phoneAssumed).toBe(false) // Country code was detected, not assumed
  })

  it('handles all common US phone number formats', () => {
    const rows = [
      ['a@test.com', '5551234567'], // Plain 10 digits
      ['b@test.com', '(555) 123-4567'], // Parentheses + dashes
      ['c@test.com', '555-123-4567'], // Dashes only
      ['d@test.com', '555.123.4567'], // Dots
      ['e@test.com', '555 123 4567'], // Spaces
      ['f@test.com', '1-555-123-4567'], // Leading 1 with dashes
      ['g@test.com', '1 (555) 123-4567'], // Leading 1 with parens
      ['h@test.com', '1.555.123.4567'], // Leading 1 with dots
      ['i@test.com', '+1 555 123 4567'], // International format
      ['j@test.com', '+1-555-123-4567'], // International with dashes
      ['k@test.com', '+1 (555) 123-4567'], // International with parens
      ['l@test.com', '1-(111)-222-3333'], // Leading 1 with parens and dashes
    ]
    const mappings = { 0: 'email' as const, 1: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings, '+1')

    // All should be valid and normalize to +15551234567 (or +11112223333 for last one)
    result.forEach((row, index) => {
      expect(row.errors).toEqual([])
      if (index < 11) {
        expect(row.phone).toBe('+15551234567')
      } else {
        expect(row.phone).toBe('+11112223333')
      }
    })
  })

  it('does not validate US format when non-US country assumed', () => {
    const rows = [['john@example.com', '728340556']] // 9 digits - valid for Poland
    const mappings = { 0: 'email' as const, 1: 'phone' as const }

    const result = parseRowsWithMappings(rows, mappings, '+48')

    expect(result[0].errors).toEqual([])
    expect(result[0].phone).toBe('+48728340556')
  })
})

describe('end-to-end CSV import scenarios', () => {
  it('imports email-only CSV', () => {
    const data = [['user1@example.com'], ['user2@example.com'], ['user3@example.com']]

    const { rows, columnMappings } = parseCsvData(data)
    const parsed = parseRowsWithMappings(rows, columnMappings)

    expect(parsed).toHaveLength(3)
    expect(parsed.every((r) => r.errors.length === 0)).toBe(true)
    expect(parsed.every((r) => r.role === 'member')).toBe(true)
  })

  it('imports name + email CSV', () => {
    const data = [
      ['Name', 'Email'],
      ['John Doe', 'john@example.com'],
      ['Jane Smith', 'jane@example.com'],
    ]

    const { rows, columnMappings } = parseCsvData(data)
    const parsed = parseRowsWithMappings(rows, columnMappings)

    expect(parsed).toHaveLength(2)
    expect(parsed[0].name).toBe('John Doe')
    expect(parsed[0].email).toBe('john@example.com')
  })

  it('imports phone + email CSV without headers', () => {
    const data = [
      ['+14155551234', 'john@example.com'],
      ['+14155559999', 'jane@example.com'],
    ]

    const { rows, columnMappings } = parseCsvData(data)
    const parsed = parseRowsWithMappings(rows, columnMappings)

    expect(parsed).toHaveLength(2)
    expect(parsed[0].phone).toBe('+14155551234')
    expect(parsed[0].email).toBe('john@example.com')
  })

  it('imports CSV with columns in any order', () => {
    const data = [
      ['Role', 'Phone', 'Name', 'Email'],
      ['admin', '+14155551234', 'John', 'john@example.com'],
    ]

    const { rows, columnMappings } = parseCsvData(data)
    const parsed = parseRowsWithMappings(rows, columnMappings)

    expect(parsed[0]).toEqual({
      email: 'john@example.com',
      name: 'John',
      phone: '+14155551234',
      rawPhone: '+14155551234',
      phoneAssumed: false,
      role: 'admin',
      errors: [],
    })
  })

  it('handles CSV with some invalid rows', () => {
    const data = [
      ['Email', 'Name'],
      ['valid@example.com', 'Valid User'],
      ['not-an-email', 'Invalid User'],
      ['another@example.com', 'Another User'],
    ]

    const { rows, columnMappings } = parseCsvData(data)
    const parsed = parseRowsWithMappings(rows, columnMappings)

    expect(parsed).toHaveLength(3)
    expect(parsed[0].errors).toEqual([])
    expect(parsed[1].errors).toContain('Invalid email format')
    expect(parsed[2].errors).toEqual([])
  })
})
