import { config } from '@/lib/env'

/** Response from create-org API */
export interface CreateOrgResponse {
  session_token: string
  session_jwt: string
}

/** API error response shape */
interface ApiErrorResponse {
  detail?: string
}

/**
 * Creates an organization via the backend API.
 */
export async function createOrganization(
  intermediateSessionToken: string,
  organizationName: string,
  organizationSlug: string
): Promise<CreateOrgResponse> {
  const res = await fetch(`${config.apiUrl}/auth/discovery/create-org`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      intermediate_session_token: intermediateSessionToken,
      organization_name: organizationName,
      organization_slug: organizationSlug,
    }),
  })

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => ({
      detail: 'Failed to create organization',
    }))) as ApiErrorResponse
    throw new Error(errorBody.detail ?? 'Failed to create organization')
  }

  return res.json() as Promise<CreateOrgResponse>
}

/**
 * Checks if an error is a name/slug conflict that can be retried.
 */
export function isConflictError(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  const message = error.message.toLowerCase()
  return message.includes('slug') || message.includes('name') || message.includes('use')
}
