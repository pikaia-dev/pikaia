import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { useApi } from '@/hooks/use-api'
import type {
  WebhookEndpointCreateRequest,
  WebhookEndpointListResponse,
  WebhookEndpointUpdateRequest,
  WebhookEndpointWithSecret,
  WebhookTestRequest,
  WebhookTestResponse,
} from '@/lib/api'
import { queryKeys } from '@/shared/query-keys'

/**
 * Mutation hook for creating a webhook endpoint.
 */
export function useCreateWebhookEndpoint() {
  const { createWebhookEndpoint } = useApi()
  const queryClient = useQueryClient()

  return useMutation<WebhookEndpointWithSecret, Error, WebhookEndpointCreateRequest>({
    mutationFn: createWebhookEndpoint,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.webhooks.endpoints(),
      })
      toast.success('Webhook endpoint created')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to create endpoint')
    },
  })
}

/**
 * Mutation hook for updating a webhook endpoint.
 */
export function useUpdateWebhookEndpoint() {
  const { updateWebhookEndpoint } = useApi()
  const queryClient = useQueryClient()

  return useMutation<
    WebhookEndpointListResponse['endpoints'][0],
    Error,
    { endpointId: string; data: WebhookEndpointUpdateRequest }
  >({
    mutationFn: ({ endpointId, data }) => updateWebhookEndpoint(endpointId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.webhooks.endpoints(),
      })
      toast.success('Webhook endpoint updated')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to update endpoint')
    },
  })
}

/**
 * Mutation hook for deleting a webhook endpoint.
 */
export function useDeleteWebhookEndpoint() {
  const { deleteWebhookEndpoint } = useApi()
  const queryClient = useQueryClient()

  return useMutation<void, Error, string>({
    mutationFn: deleteWebhookEndpoint,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.webhooks.endpoints(),
      })
      toast.success('Webhook endpoint deleted')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to delete endpoint')
    },
  })
}

/**
 * Mutation hook for testing a webhook endpoint.
 */
export function useTestWebhookEndpoint() {
  const { testWebhookEndpoint } = useApi()
  const queryClient = useQueryClient()

  return useMutation<WebhookTestResponse, Error, { endpointId: string; data: WebhookTestRequest }>({
    mutationFn: ({ endpointId, data }) => testWebhookEndpoint(endpointId, data),
    onSuccess: (response, { endpointId }) => {
      // Refresh deliveries to show the test delivery
      void queryClient.invalidateQueries({
        queryKey: queryKeys.webhooks.deliveries(endpointId),
      })
      if (response.success) {
        toast.success(`Test webhook sent (${String(response.http_status)})`)
      } else {
        toast.error(`Test failed: ${response.error_message || 'Unknown error'}`)
      }
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to send test webhook')
    },
  })
}
