import { useQuery } from '@tanstack/react-query'

import { useApi } from '@/hooks/use-api'
import type { OrganizationDetail } from '@/lib/api'
import { queryKeys } from '@/shared/query-keys'

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
