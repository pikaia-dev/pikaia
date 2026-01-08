/**
 * PaymentForm - Stripe Elements payment component.
 *
 * Renders an embedded payment form using Stripe PaymentElement.
 * Used for in-app subscription checkout without redirect.
 */

import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js"
import type { StripeElementsOptions } from "@stripe/stripe-js"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { useApi } from "../hooks/useApi"
import { getStripe } from "../lib/stripe"
import { Button } from "./ui/button"
import { LoadingSpinner } from "./ui/loading-spinner"

interface PaymentFormProps {
  quantity: number
  onSuccess: () => void
  onCancel: () => void
}

/**
 * Inner form component that uses Stripe hooks.
 * Must be wrapped in Elements provider.
 */
function PaymentFormInner({
  subscriptionId,
  onSuccess,
  onCancel,
}: {
  subscriptionId: string
  onSuccess: () => void
  onCancel: () => void
}) {
  const stripe = useStripe()
  const elements = useElements()
  const { confirmSubscription } = useApi()
  const [processing, setProcessing] = useState(false)
  const [ready, setReady] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!stripe || !elements) {
      return
    }

    setProcessing(true)

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/settings/billing?success=true`,
      },
      redirect: "if_required",
    })

    if (error) {
      toast.error(error.message || "Payment failed")
      setProcessing(false)
      return
    }

    // Payment succeeded - now sync subscription status from Stripe
    // This is needed because webhooks may not reach localhost in dev
    try {
      await confirmSubscription({ subscription_id: subscriptionId })
      toast.success("Subscription activated!")
    } catch (syncError) {
      // Sync failed but payment already went through - user should refresh
      console.error("Failed to sync subscription:", syncError)
      toast.success("Payment successful! Refreshing...")
    }

    // Always proceed - payment succeeded regardless of sync outcome
    onSuccess()
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <PaymentElement
        onReady={() => { setReady(true); }}
        options={{
          layout: "tabs",
          wallets: {
            // Disable Link since we already collect customer info
            applePay: "auto",
            googlePay: "auto",
          },
        }}
      />

      <div className="flex gap-3 justify-end pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={processing}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={!stripe || !ready || processing}>
          {processing ? (
            <>
              <LoadingSpinner size="sm" className="mr-2" />
              Processing...
            </>
          ) : (
            "Subscribe"
          )}
        </Button>
      </div>
    </form>
  )
}

/**
 * Main PaymentForm component.
 * Initializes Stripe Elements with subscription intent.
 */
export function PaymentForm({
  quantity,
  onSuccess,
  onCancel,
}: PaymentFormProps) {
  const { createSubscriptionIntent } = useApi()
  const [clientSecret, setClientSecret] = useState<string | null>(null)
  const [subscriptionId, setSubscriptionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    createSubscriptionIntent({ quantity })
      .then((response) => {
        if (!cancelled) {
          setClientSecret(response.client_secret)
          setSubscriptionId(response.subscription_id)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Failed to initialize payment"
          setError(message)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quantity]) // Note: createSubscriptionIntent excluded to prevent infinite re-renders

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="sm" />
        <span className="ml-2 text-muted-foreground">
          Setting up payment...
        </span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-destructive mb-4">{error}</p>
        <Button variant="outline" onClick={onCancel}>
          Go Back
        </Button>
      </div>
    )
  }

  if (!clientSecret || !subscriptionId) {
    return null
  }

  const options: StripeElementsOptions = {
    clientSecret,
    appearance: {
      theme: "stripe",
      variables: {
        colorPrimary: "#0f172a",
        borderRadius: "8px",
      },
    },
  }

  return (
    <Elements stripe={getStripe()} options={options}>
      <PaymentFormInner
        subscriptionId={subscriptionId}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    </Elements>
  )
}
