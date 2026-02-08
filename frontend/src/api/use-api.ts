import { useStytchB2BClient } from '@stytch/react/b2b'
import { useMemo } from 'react'

import { createApiClient } from '@/api/client'
import type {
  BillingAddress,
  BulkInviteRequest,
  BulkInviteResponse,
  CheckoutSessionRequest,
  CheckoutSessionResponse,
  ConfirmSubscriptionRequest,
  ConfirmSubscriptionResponse,
  ConfirmUploadRequest,
  ConnectedAccountsResponse,
  DeviceListResponse,
  DirectoryUser,
  EmailUpdateResponse,
  ImageResponse,
  InitiateLinkResponse,
  InviteMemberRequest,
  InviteMemberResponse,
  InvoiceListResponse,
  MemberListResponse,
  MeResponse,
  MessageResponse,
  OrganizationDetail,
  PhoneOtpResponse,
  PortalSessionRequest,
  PortalSessionResponse,
  SubscriptionInfo,
  SubscriptionIntentRequest,
  SubscriptionIntentResponse,
  UpdateMemberRoleRequest,
  UploadRequest,
  UploadResponse,
  UserInfo,
  WebhookDeliveryListResponse,
  WebhookEndpointCreateRequest,
  WebhookEndpointListResponse,
  WebhookEndpointUpdateRequest,
  WebhookEndpointWithSecret,
  WebhookEventListResponse,
  WebhookTestRequest,
  WebhookTestResponse,
} from '@/api/types'

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

  return useMemo(
    () => ({
      api,

      // Auth
      getCurrentUser: () => api.get<MeResponse>('/auth/me'),

      // Profile
      updateProfile: (data: { name: string }) => api.patch<UserInfo>('/auth/me/profile', data),

      // Phone verification
      sendPhoneOtp: (phone_number: string) =>
        api.post<PhoneOtpResponse>('/auth/phone/send-otp', { phone_number }),

      verifyPhoneOtp: (phone_number: string, otp_code: string) =>
        api.post<UserInfo>('/auth/phone/verify-otp', {
          phone_number,
          otp_code,
        }),

      // Email update
      startEmailUpdate: (new_email: string) =>
        api.post<EmailUpdateResponse>('/auth/email/start-update', {
          new_email,
        }),

      // Organization
      getOrganization: () => api.get<OrganizationDetail>('/auth/organization'),

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
      listMembers: () => api.get<MemberListResponse>('/auth/organization/members'),

      inviteMember: (data: InviteMemberRequest) =>
        api.post<InviteMemberResponse>('/auth/organization/members', data),

      bulkInviteMembers: (data: BulkInviteRequest) =>
        api.post<BulkInviteResponse>('/auth/organization/members/bulk', data),

      updateMemberRole: (memberId: number, data: UpdateMemberRoleRequest) =>
        api.patch<MessageResponse>(`/auth/organization/members/${String(memberId)}`, data),

      deleteMember: (memberId: number) =>
        api.delete<MessageResponse>(`/auth/organization/members/${String(memberId)}`),

      // Billing
      getSubscription: () => api.get<SubscriptionInfo>('/billing/subscription'),

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

      deleteImage: (imageId: string) => api.delete<MessageResponse>(`/media/${imageId}`),

      // Connected accounts
      getConnectedAccounts: () => api.get<ConnectedAccountsResponse>('/auth/me/connected-accounts'),

      disconnectProvider: (provider: string) =>
        api.delete<MessageResponse>(`/auth/me/connected-accounts/${provider}`),

      // Directory search (Google Workspace)
      searchDirectory: (q: string) =>
        api.get<DirectoryUser[]>(`/auth/directory/search?q=${encodeURIComponent(q)}`),

      // Directory avatar (fetch via authenticated request, return blob URL)
      getDirectoryAvatar: async (googleUrl: string): Promise<string | null> => {
        try {
          const response = await api.getBlob(
            `/auth/directory/avatar?url=${encodeURIComponent(googleUrl)}`
          )
          return URL.createObjectURL(response)
        } catch {
          return null
        }
      },

      // Webhooks
      listWebhookEvents: () => api.get<WebhookEventListResponse>('/webhooks/events'),

      listWebhookEndpoints: () => api.get<WebhookEndpointListResponse>('/webhooks/endpoints'),

      createWebhookEndpoint: (data: WebhookEndpointCreateRequest) =>
        api.post<WebhookEndpointWithSecret>('/webhooks/endpoints', data),

      updateWebhookEndpoint: (endpointId: string, data: WebhookEndpointUpdateRequest) =>
        api.patch<WebhookEndpointListResponse['endpoints'][0]>(
          `/webhooks/endpoints/${endpointId}`,
          data
        ),

      deleteWebhookEndpoint: (endpointId: string) =>
        api.delete<void>(`/webhooks/endpoints/${endpointId}`),

      listWebhookDeliveries: (endpointId: string, limit?: number) => {
        const query = limit ? `?limit=${String(limit)}` : ''
        return api.get<WebhookDeliveryListResponse>(
          `/webhooks/endpoints/${endpointId}/deliveries${query}`
        )
      },

      testWebhookEndpoint: (endpointId: string, data: WebhookTestRequest) =>
        api.post<WebhookTestResponse>(`/webhooks/endpoints/${endpointId}/test`, data),

      // Devices
      listDevices: () => api.get<DeviceListResponse>('/devices/'),

      initiateDeviceLink: () => api.post<InitiateLinkResponse>('/devices/link/initiate'),

      revokeDevice: (deviceId: number) => api.delete<void>(`/devices/${String(deviceId)}`),
    }),
    [api]
  )
}
