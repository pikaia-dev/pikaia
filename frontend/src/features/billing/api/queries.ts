import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import type { InvoiceListResponse, SubscriptionInfo } from '@/api/types'
import { useApi } from '@/api/use-api'

/**
 * Query hook for fetching subscription info.
 */
export function useSubscription() {
  const { getSubscription } = useApi()

  return useQuery<SubscriptionInfo>({
    queryKey: queryKeys.billing.subscription(),
    queryFn: getSubscription,
  })
}

/**
 * Query hook for fetching invoices with pagination.
 */
export function useInvoices(params?: { limit?: number; starting_after?: string }) {
  const { listInvoices } = useApi()

  return useQuery<InvoiceListResponse>({
    queryKey: queryKeys.billing.invoices(params),
    queryFn: () => listInvoices(params),
  })
}
