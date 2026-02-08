import './index.css'

import * as Sentry from '@sentry/react'
import { StytchB2BProvider } from '@stytch/react/b2b'
import { StytchB2BUIClient } from '@stytch/vanilla-js/b2b'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ErrorBoundary } from 'react-error-boundary'
import { RouterProvider } from 'react-router-dom'

import { ErrorFallback } from '@/components/error-fallback'
import { Toaster } from '@/components/ui/sonner'
import { config } from '@/lib/env'
import { router } from '@/router'

Sentry.init({
  dsn: config.sentryDsn,
  integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 1.0,
  enabled: !!config.sentryDsn,
})

// Initialize Stytch client (throws if VITE_STYTCH_PUBLIC_TOKEN is missing)
const stytchClient = new StytchB2BUIClient(config.stytchPublicToken)

// Initialize React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root element not found')
}

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={(error, info) =>
        Sentry.captureException(error, { extra: { componentStack: info.componentStack } })
      }
    >
      <StytchB2BProvider stytch={stytchClient}>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
          <Toaster richColors position="top-right" />
        </QueryClientProvider>
      </StytchB2BProvider>
    </ErrorBoundary>
  </StrictMode>
)
