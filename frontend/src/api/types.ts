/**
 * API response types matching backend schemas.
 */

// User & Auth types
export interface UserInfo {
  id: number
  email: string
  name: string
  avatar_url: string
  phone_number: string
}

export interface MemberInfo {
  id: number
  stytch_member_id: string
  role: string
  is_admin: boolean
}

export interface OrganizationInfo {
  id: number
  stytch_org_id: string
  name: string
  slug: string
  logo_url: string
}

export interface MeResponse {
  user: UserInfo
  member: MemberInfo
  organization: OrganizationInfo
}

// Phone verification types
export interface PhoneOtpResponse {
  success: boolean
  message: string
}

// Email update types
export interface EmailUpdateResponse {
  success: boolean
  message: string
}

// Organization settings types
export interface BillingAddress {
  line1: string
  line2: string
  city: string
  state: string
  postal_code: string
  country: string
}

export interface BillingInfo {
  use_billing_email: boolean
  billing_email: string
  billing_name: string
  address: BillingAddress
  vat_id: string
}

export interface OrganizationDetail {
  id: number
  stytch_org_id: string
  name: string
  slug: string
  logo_url: string
  billing: BillingInfo
}

// Member management types
export interface MemberListItem {
  id: number
  stytch_member_id: string
  email: string
  name: string
  role: string
  is_admin: boolean
  status: string
  created_at: string
}

export interface MemberListResponse {
  members: MemberListItem[]
}

export interface InviteMemberRequest {
  email: string
  name?: string
  role?: 'admin' | 'member'
}

export interface InviteMemberResponse {
  message: string
  stytch_member_id: string
}

export interface UpdateMemberRoleRequest {
  role: 'admin' | 'member'
}

export interface MessageResponse {
  message: string
}

// Billing/Subscription types
export interface SubscriptionInfo {
  status: 'active' | 'past_due' | 'canceled' | 'incomplete' | 'trialing' | 'none'
  quantity: number
  current_period_end: string | null
  cancel_at_period_end: boolean
  stripe_customer_id: string | null
}

export interface CheckoutSessionRequest {
  success_url: string
  cancel_url: string
  quantity?: number
}

export interface CheckoutSessionResponse {
  checkout_url: string
}

export interface PortalSessionRequest {
  return_url: string
}

export interface PortalSessionResponse {
  portal_url: string
}

export interface SubscriptionIntentRequest {
  quantity?: number
}

export interface SubscriptionIntentResponse {
  client_secret: string
  subscription_id: string
}

export interface ConfirmSubscriptionRequest {
  subscription_id: string
}

export interface ConfirmSubscriptionResponse {
  is_active: boolean
}

// Invoice types
export interface Invoice {
  id: string
  number: string | null
  status: 'draft' | 'open' | 'paid' | 'uncollectible' | 'void'
  amount_due: number // cents
  amount_paid: number // cents
  currency: string
  created: string // ISO timestamp
  hosted_invoice_url: string | null
  invoice_pdf: string | null
  period_start: string | null
  period_end: string | null
}

export interface InvoiceListResponse {
  invoices: Invoice[]
  has_more: boolean
}

// Media upload types
export interface UploadRequest {
  filename: string
  content_type: string
  size_bytes: number
  image_type: 'avatar' | 'logo'
}

export interface UploadResponse {
  upload_url: string
  method: 'PUT' | 'POST'
  key: string
  fields: Record<string, string>
}

export interface ConfirmUploadRequest {
  key: string
  image_type: 'avatar' | 'logo'
}

export interface ImageResponse {
  id: string
  url: string
  width: number | null
  height: number | null
}

// Directory search types (Google Workspace)
export interface DirectoryUser {
  email: string
  name: string
  avatar_url: string
}

// Bulk invite types
export interface BulkInviteMemberItem {
  email: string
  name?: string
  phone?: string
  role?: 'admin' | 'member'
}

export interface BulkInviteRequest {
  members: BulkInviteMemberItem[]
}

export interface BulkInviteResultItem {
  email: string
  success: boolean
  error: string | null
  stytch_member_id: string | null
}

export interface BulkInviteResponse {
  results: BulkInviteResultItem[]
  total: number
  succeeded: number
  failed: number
}

// Webhook types
export interface WebhookEndpoint {
  id: string
  name: string
  description: string
  url: string
  events: string[]
  active: boolean
  last_delivery_status: string
  last_delivery_at: string | null
  consecutive_failures: number
  created_at: string
  updated_at: string
}

export interface WebhookEndpointWithSecret extends WebhookEndpoint {
  secret: string
}

export interface WebhookEndpointListResponse {
  endpoints: WebhookEndpoint[]
}

export interface WebhookEndpointCreateRequest {
  name: string
  description?: string
  url: string
  events: string[]
}

export interface WebhookEndpointUpdateRequest {
  name?: string
  description?: string
  url?: string
  events?: string[]
  active?: boolean
}

export interface WebhookDelivery {
  id: string
  event_id: string
  event_type: string
  status: 'pending' | 'success' | 'failure'
  error_type: string
  http_status: number | null
  duration_ms: number | null
  response_snippet: string
  attempt_number: number
  attempted_at: string | null
  created_at: string
}

export interface WebhookDeliveryListResponse {
  deliveries: WebhookDelivery[]
}

export interface WebhookEventType {
  type: string
  description: string
  category: string
  payload_example: Record<string, unknown>
}

export interface WebhookEventListResponse {
  events: WebhookEventType[]
}

export interface WebhookTestRequest {
  event_type: string
}

export interface WebhookTestResponse {
  success: boolean
  http_status: number | null
  duration_ms: number | null
  signature: string
  response_snippet: string
  error_message: string
}

// Device types
export interface DeviceResponse {
  id: number
  name: string
  platform: string
  os_version: string
  app_version: string
  created_at: string
}

export interface DeviceListResponse {
  devices: DeviceResponse[]
  count: number
}

export interface InitiateLinkResponse {
  qr_url: string
  expires_at: string
  expires_in_seconds: number
}
