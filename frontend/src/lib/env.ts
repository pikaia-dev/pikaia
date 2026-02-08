/**
 * Typed environment variable helper.
 * Validates required VITE_* variables at runtime and centralizes config.
 */

export function getEnv(key: keyof ImportMetaEnv, fallback?: string): string {
  const val = import.meta.env[key] as string | undefined
  if (val && val !== '') return val
  if (fallback !== undefined) return fallback
  throw new Error(`Missing required env: ${String(key)}`)
}

// Centralized config - validates on import
export const config = {
  stytchPublicToken: getEnv('VITE_STYTCH_PUBLIC_TOKEN'),
  apiUrl: getEnv('VITE_API_URL', 'http://localhost:8000/api/v1'),
  stripePublishableKey: getEnv('VITE_STRIPE_PUBLISHABLE_KEY', ''),
  sentryDsn: getEnv('VITE_SENTRY_DSN', ''),
} as const
