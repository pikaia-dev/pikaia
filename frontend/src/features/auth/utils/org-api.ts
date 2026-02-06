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

/** Error subclass that carries the HTTP status code from the response. */
export class ApiResponseError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiResponseError'
    this.status = status
  }
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
    throw new ApiResponseError(errorBody.detail ?? 'Failed to create organization', res.status)
  }

  return res.json() as Promise<CreateOrgResponse>
}

/**
 * Checks if an error is a name/slug conflict (HTTP 409) that can be retried.
 */
export function isConflictError(error: unknown): boolean {
  return error instanceof ApiResponseError && error.status === 409
}
