import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiResponseError,
  createOrganization,
  isConflictError,
} from '@/features/auth/utils/org-api'

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

  it('throws ApiResponseError with detail message and status on failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({
          detail: 'Organization slug already exists',
        }),
    })

    const promise = createOrganization('ist_123', 'My Org', 'my-org')
    await expect(promise).rejects.toBeInstanceOf(ApiResponseError)
    await expect(promise).rejects.toMatchObject({
      message: 'Organization slug already exists',
      status: 409,
    })
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
  it('returns true for ApiResponseError with status 409', () => {
    expect(isConflictError(new ApiResponseError('Organization slug already exists', 409))).toBe(
      true
    )
    expect(isConflictError(new ApiResponseError('Name already in use', 409))).toBe(true)
  })

  it('returns false for ApiResponseError with non-409 status', () => {
    expect(isConflictError(new ApiResponseError('Not found', 404))).toBe(false)
    expect(isConflictError(new ApiResponseError('Server error', 500))).toBe(false)
    expect(isConflictError(new ApiResponseError('Unauthorized', 401))).toBe(false)
  })

  it('returns false for plain Error objects', () => {
    expect(isConflictError(new Error('Organization slug already exists'))).toBe(false)
    expect(isConflictError(new Error('Network error'))).toBe(false)
  })

  it('returns false for non-Error objects', () => {
    expect(isConflictError('slug error')).toBe(false)
    expect(isConflictError({ message: 'slug error' })).toBe(false)
    expect(isConflictError(null)).toBe(false)
    expect(isConflictError(undefined)).toBe(false)
  })
})
