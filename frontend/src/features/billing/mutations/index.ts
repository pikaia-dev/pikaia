import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { useApi } from '@/hooks/use-api'
import type {
  CheckoutSessionRequest,
  ConfirmSubscriptionRequest,
  PortalSessionRequest,
} from '@/lib/api'
import { queryKeys } from '@/shared/query-keys'

/**
 * Mutation hook for creating a checkout session.
 */
export function useCreateCheckoutSession() {
  const { createCheckoutSession } = useApi()

  return useMutation({
    mutationFn: (data: CheckoutSessionRequest) => createCheckoutSession(data),
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create checkout')
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
      toast.error(error.message || 'Failed to open billing portal')
    },
  })
}

/**
 * Mutation hook for confirming subscription after payment.
 * Syncs subscription status from Stripe (useful when webhooks may be delayed).
 */
export function useConfirmSubscription() {
  const { confirmSubscription } = useApi()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ConfirmSubscriptionRequest) => confirmSubscription(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.billing.subscription(),
      })
      toast.success('Subscription activated!')
    },
    onError: () => {
      // Sync failed but payment likely succeeded - still invalidate to let webhook catch up
      void queryClient.invalidateQueries({
        queryKey: queryKeys.billing.subscription(),
      })
      toast.error(
        "Payment received, but we couldn't confirm your subscription yet. It should update shortly."
      )
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
