import { useQuery } from '@tanstack/react-query'

import { useApi } from '@/hooks/use-api'
import type {
  WebhookDeliveryListResponse,
  WebhookEndpointListResponse,
  WebhookEventListResponse,
} from '@/lib/api'
import { queryKeys } from '@/shared/query-keys'

/**
 * Query hook for fetching available webhook events.
 */
export function useWebhookEvents() {
  const { listWebhookEvents } = useApi()

  return useQuery<WebhookEventListResponse>({
    queryKey: queryKeys.webhooks.events(),
    queryFn: listWebhookEvents,
    staleTime: 5 * 60 * 1000, // Events catalog is static, cache for 5 min
  })
}

/**
 * Query hook for fetching webhook endpoints.
 */
export function useWebhookEndpoints() {
  const { listWebhookEndpoints } = useApi()

  return useQuery<WebhookEndpointListResponse>({
    queryKey: queryKeys.webhooks.endpoints(),
    queryFn: listWebhookEndpoints,
  })
}

/**
 * Query hook for fetching webhook deliveries for an endpoint.
 */
export function useWebhookDeliveries(endpointId: string, limit?: number) {
  const { listWebhookDeliveries } = useApi()

  return useQuery<WebhookDeliveryListResponse>({
    queryKey: queryKeys.webhooks.deliveries(endpointId),
    queryFn: () => listWebhookDeliveries(endpointId, limit),
    enabled: Boolean(endpointId),
  })
}
