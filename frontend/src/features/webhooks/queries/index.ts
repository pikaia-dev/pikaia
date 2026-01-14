import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { useApi } from "../../../hooks/useApi"
import type {
    WebhookDeliveryListResponse,
    WebhookEndpointCreateRequest,
    WebhookEndpointListResponse,
    WebhookEndpointUpdateRequest,
    WebhookEndpointWithSecret,
    WebhookEventListResponse,
    WebhookTestRequest,
    WebhookTestResponse,
} from "../../../lib/api"
import { queryKeys } from "../../shared/query-keys"

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

/**
 * Mutation hook for creating a webhook endpoint.
 */
export function useCreateWebhookEndpoint() {
    const { createWebhookEndpoint } = useApi()
    const queryClient = useQueryClient()

    return useMutation<
        WebhookEndpointWithSecret,
        Error,
        WebhookEndpointCreateRequest
    >({
        mutationFn: createWebhookEndpoint,
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: queryKeys.webhooks.endpoints(),
            })
            toast.success("Webhook endpoint created")
        },
        onError: (error) => {
            toast.error(error.message || "Failed to create endpoint")
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
        WebhookEndpointListResponse["endpoints"][0],
        Error,
        { endpointId: string; data: WebhookEndpointUpdateRequest }
    >({
        mutationFn: ({ endpointId, data }) =>
            updateWebhookEndpoint(endpointId, data),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: queryKeys.webhooks.endpoints(),
            })
            toast.success("Webhook endpoint updated")
        },
        onError: (error) => {
            toast.error(error.message || "Failed to update endpoint")
        },
    })
}

/**
 * Mutation hook for deleting a webhook endpoint.
 */
export function useDeleteWebhookEndpoint() {
    const { deleteWebhookEndpoint } = useApi()
    const queryClient = useQueryClient()

    return useMutation<undefined, Error, string>({
        mutationFn: deleteWebhookEndpoint,
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: queryKeys.webhooks.endpoints(),
            })
            toast.success("Webhook endpoint deleted")
        },
        onError: (error) => {
            toast.error(error.message || "Failed to delete endpoint")
        },
    })
}

/**
 * Mutation hook for testing a webhook endpoint.
 */
export function useTestWebhookEndpoint() {
    const { testWebhookEndpoint } = useApi()
    const queryClient = useQueryClient()

    return useMutation<
        WebhookTestResponse,
        Error,
        { endpointId: string; data: WebhookTestRequest }
    >({
        mutationFn: ({ endpointId, data }) =>
            testWebhookEndpoint(endpointId, data),
        onSuccess: (response, { endpointId }) => {
            // Refresh deliveries to show the test delivery
            void queryClient.invalidateQueries({
                queryKey: queryKeys.webhooks.deliveries(endpointId),
            })
            if (response.success) {
                toast.success(`Test webhook sent (${String(response.http_status)})`)
            } else {
                toast.error(`Test failed: ${response.error_message || "Unknown error"}`)
            }
        },
        onError: (error) => {
            toast.error(error.message || "Failed to send test webhook")
        },
    })
}
