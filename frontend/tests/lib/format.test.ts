import { describe, expect, it } from 'vitest'

import { formatDateLong, formatDateShort, formatDateTime } from '@/lib/format'

describe('formatDateShort', () => {
  it('formats date to short format (MMM d, yyyy)', () => {
    const result = formatDateShort('2026-01-24T17:48:31.373Z')
    expect(result).toBe('Jan 24, 2026')
  })

  it('returns dash for null input', () => {
    expect(formatDateShort(null)).toBe('—')
  })

  it('handles different months correctly', () => {
    expect(formatDateShort('2026-12-01T00:00:00Z')).toBe('Dec 1, 2026')
    expect(formatDateShort('2026-06-15T00:00:00Z')).toBe('Jun 15, 2026')
  })
})

describe('formatDateLong', () => {
  it('formats date to long format (MMMM d, yyyy)', () => {
    const result = formatDateLong('2026-01-24T17:48:31.373Z')
    expect(result).toBe('January 24, 2026')
  })

  it('returns dash for null input', () => {
    expect(formatDateLong(null)).toBe('—')
  })

  it('handles different months correctly', () => {
    expect(formatDateLong('2026-12-01T00:00:00Z')).toBe('December 1, 2026')
    expect(formatDateLong('2026-06-15T00:00:00Z')).toBe('June 15, 2026')
  })
})

describe('formatDateTime', () => {
  it('formats date to full datetime', () => {
    const result = formatDateTime('2026-01-24T17:48:31.373Z')
    // Full datetime format varies by locale, so just check it contains the date parts
    expect(result).toContain('2026')
    expect(result).toContain('24')
  })

  it('returns dash for null input', () => {
    expect(formatDateTime(null)).toBe('—')
  })

  it('includes time component', () => {
    const result = formatDateTime('2026-01-24T14:30:00.000Z')
    // Should contain some time representation (varies by locale/timezone)
    expect(result.length).toBeGreaterThan(10) // More than just a date
  })
})
