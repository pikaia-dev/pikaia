/**
 * API client with authentication.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

interface ApiError {
    detail: string
}

class ApiClient {
    private getAuthToken(): string | null {
        // Get Stytch session JWT from cookies
        // The Stytch SDK stores it in a cookie named 'stytch_session_jwt'
        const cookies = document.cookie.split(';')
        for (const cookie of cookies) {
            const [name, value] = cookie.trim().split('=')
            if (name === 'stytch_session_jwt') {
                return value
            }
        }
        return null
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const token = this.getAuthToken()

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

    async get<T>(endpoint: string): Promise<T> {
        return this.request<T>(endpoint, { method: 'GET' })
    }

    async post<T>(endpoint: string, data?: unknown): Promise<T> {
        return this.request<T>(endpoint, {
            method: 'POST',
            body: data ? JSON.stringify(data) : undefined,
        })
    }
}

export const api = new ApiClient()

// API types matching backend schemas
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

// API functions
export async function getCurrentUser(): Promise<MeResponse> {
    return api.get<MeResponse>('/auth/me')
}
