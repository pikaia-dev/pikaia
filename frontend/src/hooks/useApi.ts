import { useMemo } from 'react'
import { useStytchB2BClient } from '@stytch/react/b2b'
import {
    createApiClient,
    type MeResponse,
    type OrganizationDetail,
    type UserInfo,
    type BillingAddress,
    type MemberListResponse,
    type InviteMemberRequest,
    type InviteMemberResponse,
    type UpdateMemberRoleRequest,
    type MessageResponse,
    type SubscriptionInfo,
    type CheckoutSessionRequest,
    type CheckoutSessionResponse,
    type PortalSessionRequest,
    type PortalSessionResponse,
    type SubscriptionIntentRequest,
    type SubscriptionIntentResponse,
    type ConfirmSubscriptionRequest,
    type ConfirmSubscriptionResponse,
} from '../lib/api'

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
            use_billing_email: boolean
            billing_email?: string
            billing_name: string
            address?: BillingAddress
            vat_id: string
        }) => api.patch<OrganizationDetail>('/auth/organization/billing', data),

        // Members
        listMembers: () =>
            api.get<MemberListResponse>('/auth/organization/members'),

        inviteMember: (data: InviteMemberRequest) =>
            api.post<InviteMemberResponse>('/auth/organization/members', data),

        updateMemberRole: (memberId: number, data: UpdateMemberRoleRequest) =>
            api.patch<MessageResponse>(`/auth/organization/members/${memberId}`, data),

        deleteMember: (memberId: number) =>
            api.delete<MessageResponse>(`/auth/organization/members/${memberId}`),

        // Billing
        getSubscription: () =>
            api.get<SubscriptionInfo>('/billing/subscription'),

        createCheckoutSession: (data: CheckoutSessionRequest) =>
            api.post<CheckoutSessionResponse>('/billing/checkout', data),

        createPortalSession: (data: PortalSessionRequest) =>
            api.post<PortalSessionResponse>('/billing/portal', data),

        createSubscriptionIntent: (data: SubscriptionIntentRequest) =>
            api.post<SubscriptionIntentResponse>('/billing/subscription-intent', data),

        confirmSubscription: (data: ConfirmSubscriptionRequest) =>
            api.post<ConfirmSubscriptionResponse>('/billing/confirm-subscription', data),
    }), [api])
}

