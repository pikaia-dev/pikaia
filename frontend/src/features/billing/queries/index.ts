import { useQuery } from '@tanstack/react-query'

import { useApi } from '@/hooks/use-api'
import type { InvoiceListResponse, SubscriptionInfo } from '@/lib/api'
import { queryKeys } from '@/shared/query-keys'

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
