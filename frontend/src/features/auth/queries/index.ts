import { useQuery } from '@tanstack/react-query'

import { useApi } from '../../../hooks/useApi'
import type { MeResponse } from '../../../lib/api'
import { queryKeys } from '../../shared/query-keys'

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
