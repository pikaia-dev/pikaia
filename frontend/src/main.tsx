import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StytchB2BProvider } from '@stytch/react/b2b'
import { StytchB2BUIClient } from '@stytch/vanilla-js/b2b'
import App from './App.tsx'
import './index.css'

// Initialize Stytch client
const stytchClient = new StytchB2BUIClient(
  import.meta.env.VITE_STYTCH_PUBLIC_TOKEN || ''
)

// Initialize React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <StytchB2BProvider stytch={stytchClient}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StytchB2BProvider>
  </StrictMode>,
)
