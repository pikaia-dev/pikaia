import { useQuery } from '@tanstack/react-query'

import { useApi } from '@/hooks/use-api'
import type { MemberListResponse } from '@/lib/api'
import { queryKeys } from '@/shared/query-keys'

/**
 * Query hook for fetching organization members.
 */
export function useMembers() {
  const { listMembers } = useApi()

  return useQuery<MemberListResponse>({
    queryKey: queryKeys.members.list(),
    queryFn: listMembers,
  })
}
