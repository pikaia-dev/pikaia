import { useMemo } from 'react'
import { useStytchB2BClient } from '@stytch/react/b2b'
import { createApiClient, type MeResponse } from '../lib/api'

/**
 * Hook that provides an authenticated API client using the Stytch SDK.
 * 
 * Uses session.getTokens() from the SDK which:
 * - Returns { session_token, session_jwt } when HttpOnly is disabled
 * - Returns null when HttpOnly is enabled (explicit failure)
 * - Is maintained by Stytch and handles any cookie format changes
 * 
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { api, getCurrentUser } = useApi()
 *   
 *   // Use convenience methods
 *   const user = await getCurrentUser()
 *   
 *   // Or use the raw client
 *   const data = await api.get<MyType>('/my-endpoint')
 * }
 * ```
 */
export function useApi() {
    const stytch = useStytchB2BClient()

    const api = useMemo(() => {
        const tokenProvider = () => {
            // Use the SDK's official method to get tokens
            // This returns null if HttpOnly cookies are enabled
            const tokens = stytch.session.getTokens()
            return tokens?.session_jwt ?? null
        }

        return createApiClient(tokenProvider)
    }, [stytch])

    // Convenience API methods
    const getCurrentUser = useMemo(() => {
        return () => api.get<MeResponse>('/auth/me')
    }, [api])

    return {
        api,
        getCurrentUser,
    }
}
