import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import type { MemberListResponse } from '@/api/types'
import { useApi } from '@/api/use-api'

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
