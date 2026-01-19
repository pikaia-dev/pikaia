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

interface ApiError {
  detail: string
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
      const error = (await response.json().catch(
        (): ApiError => ({
          detail: 'An error occurred',
        })
      )) as ApiError
      throw new Error(error.detail)
    }

    return response.json() as Promise<T>
  }

  return {
    get<T>(endpoint: string): Promise<T> {
      return request<T>(endpoint, { method: 'GET' })
    },

    post<T>(endpoint: string, data?: unknown): Promise<T> {
      return request<T>(endpoint, {
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined,
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
        throw new Error('Failed to fetch blob')
      }
      return response.blob()
    },
  }
}
