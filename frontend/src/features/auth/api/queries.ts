import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import type { MeResponse } from '@/api/types'
import { useApi } from '@/api/use-api'

/**
 * Query hook for fetching the current authenticated user.
 *
 * Returns user, member, and organization data from /auth/me endpoint.
 * Automatically caches and deduplicates requests.
 */
export function useCurrentUser() {
  const { getCurrentUser } = useApi()

  return useQuery<MeResponse>({
    queryKey: queryKeys.auth.me(),
    queryFn: getCurrentUser,
  })
}
