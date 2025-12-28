import { useMemo } from 'react'
import { useStytchB2BClient } from '@stytch/react/b2b'
import { createApiClient, type MeResponse, type OrganizationDetail, type UserInfo, type BillingAddress } from '../lib/api'

/**
 * Hook that provides an authenticated API client using the Stytch SDK.
 */
export function useApi() {
    const stytch = useStytchB2BClient()

    const api = useMemo(() => {
        const tokenProvider = () => {
            const tokens = stytch.session.getTokens()
            return tokens?.session_jwt ?? null
        }

        return createApiClient(tokenProvider)
    }, [stytch])

    return useMemo(() => ({
        api,

        // Auth
        getCurrentUser: () => api.get<MeResponse>('/auth/me'),

        // Profile
        updateProfile: (data: { name: string }) =>
            api.patch<UserInfo>('/auth/me/profile', data),

        // Organization
        getOrganization: () =>
            api.get<OrganizationDetail>('/auth/organization'),

        updateOrganization: (data: { name: string }) =>
            api.patch<OrganizationDetail>('/auth/organization', data),

        updateBilling: (data: {
            billing_email?: string
            billing_name: string
            address?: BillingAddress
            vat_id: string
        }) => api.patch<OrganizationDetail>('/auth/organization/billing', data),
    }), [api])
}

