/**
 * API client with token provider pattern for authentication.
 *
 * Token sourcing is centralized and uses the Stytch SDK's session.getTokens()
 * method rather than parsing document.cookie directly. This approach:
 * - Uses the official SDK API (maintained by Stytch)
 * - Fails explicitly if HttpOnly cookies are enabled
 * - Is more secure and maintainable
 */

import { config } from '@/lib/env'

const API_URL = config.apiUrl

interface ApiErrorBody {
  detail: string
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Token provider function type.
 * Returns JWT token string or null if no session.
 */
export type TokenProvider = () => string | null

/**
 * Creates an API client with the given token provider.
 * This allows swapping token sourcing without touching client internals.
 */
export function createApiClient(getToken: TokenProvider) {
  async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = getToken()

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
      credentials: 'include',
    })

    if (!response.ok) {
      const body = (await response.json().catch(
        (): ApiErrorBody => ({
          detail: 'An error occurred',
        })
      )) as ApiErrorBody
      throw new ApiError(body.detail, response.status)
    }

    // Handle empty-body responses (204 No Content, 205 Reset Content)
    if (response.status === 204 || response.status === 205) {
      return undefined as T
    }

    // Guard against non-JSON responses (e.g. HTML served by CDN/proxy fallback)
    const contentType = response.headers.get('content-type') ?? ''
    if (!contentType.includes('application/json')) {
      throw new ApiError('Expected JSON response from API but received a non-JSON response', 502)
    }

    return response.json() as Promise<T>
  }

  return {
    get<T>(endpoint: string): Promise<T> {
      return request<T>(endpoint, { method: 'GET' })
    },

    post<T>(endpoint: string, data?: unknown, options?: { signal?: AbortSignal }): Promise<T> {
      return request<T>(endpoint, {
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined,
        signal: options?.signal,
      })
    },

    put<T>(endpoint: string, data?: unknown): Promise<T> {
      return request<T>(endpoint, {
        method: 'PUT',
        body: data ? JSON.stringify(data) : undefined,
      })
    },

    delete<T>(endpoint: string): Promise<T> {
      return request<T>(endpoint, { method: 'DELETE' })
    },

    patch<T>(endpoint: string, data?: unknown): Promise<T> {
      return request<T>(endpoint, {
        method: 'PATCH',
        body: data ? JSON.stringify(data) : undefined,
      })
    },

    async getBlob(endpoint: string): Promise<Blob> {
      const token = getToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'GET',
        headers,
        credentials: 'include',
      })
      if (!response.ok) {
        throw new ApiError('Failed to fetch blob', response.status)
      }
      return response.blob()
    },
  }
}
