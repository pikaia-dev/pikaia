import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import type { OrganizationDetail } from '@/api/types'
import { useApi } from '@/api/use-api'

/**
 * Query hook for fetching the current organization details.
 */
export function useOrganization() {
  const { getOrganization } = useApi()

  return useQuery<OrganizationDetail>({
    queryKey: queryKeys.organization.detail(),
    queryFn: getOrganization,
  })
}
