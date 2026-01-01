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
    type InvoiceListResponse,
    type UploadRequest,
    type UploadResponse,
    type ConfirmUploadRequest,
    type ImageResponse,
    type PhoneOtpResponse,
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

        // Phone verification
        sendPhoneOtp: (phone_number: string) =>
            api.post<PhoneOtpResponse>('/auth/phone/send-otp', { phone_number }),

        verifyPhoneOtp: (phone_number: string, otp_code: string) =>
            api.post<UserInfo>('/auth/phone/verify-otp', { phone_number, otp_code }),

        // Organization
        getOrganization: () =>
            api.get<OrganizationDetail>('/auth/organization'),

        updateOrganization: (data: { name: string; slug?: string }) =>
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

        listInvoices: (params?: { limit?: number; starting_after?: string }) => {
            const queryParams = new URLSearchParams()
            if (params?.limit) queryParams.set('limit', params.limit.toString())
            if (params?.starting_after) queryParams.set('starting_after', params.starting_after)
            const query = queryParams.toString()
            return api.get<InvoiceListResponse>(`/billing/invoices${query ? `?${query}` : ''}`)
        },

        // Media
        requestUpload: (data: UploadRequest) =>
            api.post<UploadResponse>('/media/upload-request', data),

        confirmUpload: (data: ConfirmUploadRequest) =>
            api.post<ImageResponse>('/media/confirm', data),

        deleteImage: (imageId: string) =>
            api.delete<MessageResponse>(`/media/${imageId}`),
    }), [api])
}

