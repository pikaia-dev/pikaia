/**
 * Stripe provider for Elements integration.
 * Initializes Stripe.js and provides context for payment forms.
 */

import { loadStripe, type Stripe } from '@stripe/stripe-js'
import { config } from './env'

let stripePromise: Promise<Stripe | null> | null = null

/**
 * Get the Stripe instance (singleton pattern).
 * Returns null if publishable key is not configured.
 */
export function getStripe(): Promise<Stripe | null> {
    if (!config.stripePublishableKey) {
        console.warn('VITE_STRIPE_PUBLISHABLE_KEY not configured')
        return Promise.resolve(null)
    }

    if (!stripePromise) {
        stripePromise = loadStripe(config.stripePublishableKey)
    }
    return stripePromise
}
