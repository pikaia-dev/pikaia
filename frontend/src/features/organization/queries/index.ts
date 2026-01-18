import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { useApi } from '../../../hooks/useApi'
import type { BillingAddress, OrganizationDetail } from '../../../lib/api'
import { queryKeys } from '../../shared/query-keys'

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

/**
 * Mutation hook for updating organization name and slug.
 */
export function useUpdateOrganization() {
  const { updateOrganization } = useApi()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: { name: string; slug?: string }) => updateOrganization(data),
    onSuccess: (updatedOrg) => {
      // Update cache with new data
      queryClient.setQueryData(queryKeys.organization.detail(), updatedOrg)
      toast.success('Organization updated')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update organization')
    },
  })
}

/**
 * Mutation hook for updating organization billing info.
 */
export function useUpdateBilling() {
  const { updateBilling } = useApi()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: {
      use_billing_email: boolean
      billing_email?: string
      billing_name: string
      address?: BillingAddress
      vat_id: string
    }) => updateBilling(data),
    onSuccess: (updatedOrg) => {
      queryClient.setQueryData(queryKeys.organization.detail(), updatedOrg)
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update billing')
    },
  })
}
