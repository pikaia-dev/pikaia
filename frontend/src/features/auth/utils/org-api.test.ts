import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createOrganization, isConflictError } from './org-api'

// Mock the env module
vi.mock('@/lib/env', () => ({
  config: {
    apiUrl: 'http://localhost:8000/api/v1',
  },
}))

describe('createOrganization', () => {
  const mockFetch = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    mockFetch.mockReset()
  })

  it('calls the correct endpoint with proper payload', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          session_token: 'token123',
          session_jwt: 'jwt123',
        }),
    })

    await createOrganization('ist_123', 'My Org', 'my-org')

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/auth/discovery/create-org',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          intermediate_session_token: 'ist_123',
          organization_name: 'My Org',
          organization_slug: 'my-org',
        }),
      }
    )
  })

  it('returns session tokens on success', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          session_token: 'token123',
          session_jwt: 'jwt123',
        }),
    })

    const result = await createOrganization('ist_123', 'My Org', 'my-org')

    expect(result).toEqual({
      session_token: 'token123',
      session_jwt: 'jwt123',
    })
  })

  it('throws error with detail message on failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          detail: 'Organization slug already exists',
        }),
    })

    await expect(createOrganization('ist_123', 'My Org', 'my-org')).rejects.toThrow(
      'Organization slug already exists'
    )
  })

  it('throws default error when response has no detail', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({}),
    })

    await expect(createOrganization('ist_123', 'My Org', 'my-org')).rejects.toThrow(
      'Failed to create organization'
    )
  })

  it('throws default error when JSON parsing fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.reject(new Error('Invalid JSON')),
    })

    await expect(createOrganization('ist_123', 'My Org', 'my-org')).rejects.toThrow(
      'Failed to create organization'
    )
  })
})

describe('isConflictError', () => {
  it('returns true for slug conflict errors', () => {
    expect(isConflictError(new Error('Organization slug already exists'))).toBe(true)
    expect(isConflictError(new Error('This slug is taken'))).toBe(true)
  })

  it('returns true for name conflict errors', () => {
    expect(isConflictError(new Error('Organization name already exists'))).toBe(true)
    expect(isConflictError(new Error('This name is in use'))).toBe(true)
  })

  it("returns true for generic 'use' conflict errors", () => {
    expect(isConflictError(new Error('Cannot use this identifier'))).toBe(true)
    expect(isConflictError(new Error('Already in use'))).toBe(true)
  })

  it('returns false for non-conflict errors', () => {
    expect(isConflictError(new Error('Network error'))).toBe(false)
    expect(isConflictError(new Error('Unauthorized'))).toBe(false)
    expect(isConflictError(new Error('Server error'))).toBe(false)
  })

  it('returns false for non-Error objects', () => {
    expect(isConflictError('slug error')).toBe(false)
    expect(isConflictError({ message: 'slug error' })).toBe(false)
    expect(isConflictError(null)).toBe(false)
    expect(isConflictError(undefined)).toBe(false)
  })

  it('is case-insensitive', () => {
    expect(isConflictError(new Error('SLUG already exists'))).toBe(true)
    expect(isConflictError(new Error('NAME conflict'))).toBe(true)
    expect(isConflictError(new Error('In USE'))).toBe(true)
  })
})
