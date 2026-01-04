import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { useApi } from "../../../hooks/useApi"
import type {
    CheckoutSessionRequest,
    InvoiceListResponse,
    PortalSessionRequest,
    SubscriptionInfo,
} from "../../../lib/api"
import { queryKeys } from "../../shared/query-keys"

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
export function useInvoices(params?: {
    limit?: number
    starting_after?: string
}) {
    const { listInvoices } = useApi()

    return useQuery<InvoiceListResponse>({
        queryKey: queryKeys.billing.invoices(params),
        queryFn: () => listInvoices(params),
    })
}

/**
 * Mutation hook for creating a checkout session.
 */
export function useCreateCheckoutSession() {
    const { createCheckoutSession } = useApi()

    return useMutation({
        mutationFn: (data: CheckoutSessionRequest) => createCheckoutSession(data),
        onError: (error: Error) => {
            toast.error(error.message || "Failed to create checkout")
        },
    })
}

/**
 * Mutation hook for creating a portal session.
 */
export function useCreatePortalSession() {
    const { createPortalSession } = useApi()

    return useMutation({
        mutationFn: (data: PortalSessionRequest) => createPortalSession(data),
        onError: (error: Error) => {
            toast.error(error.message || "Failed to open billing portal")
        },
    })
}

/**
 * Hook to refresh subscription data after upgrade.
 */
export function useRefreshSubscription() {
    const queryClient = useQueryClient()

    return () => {
        void queryClient.invalidateQueries({
            queryKey: queryKeys.billing.subscription(),
        })
    }
}
