/**
 * API client with token provider pattern for authentication.
 * 
 * Token sourcing is centralized and uses the Stytch SDK's session.getTokens()
 * method rather than parsing document.cookie directly. This approach:
 * - Uses the official SDK API (maintained by Stytch)
 * - Fails explicitly if HttpOnly cookies are enabled
 * - Is more secure and maintainable
 */

import { config } from './env'

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
    async function request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const token = getToken()

        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        }

        if (token) {
            headers['Authorization'] = `Bearer ${token}`
        }

        const response = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers,
        })

        if (!response.ok) {
            const error: ApiError = await response.json().catch(() => ({
                detail: 'An error occurred',
            }))
            throw new Error(error.detail)
        }

        return response.json()
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
    }
}

// API response types matching backend schemas
export interface UserInfo {
    id: number
    email: string
    name: string
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
}

export interface MeResponse {
    user: UserInfo
    member: MemberInfo
    organization: OrganizationInfo
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
