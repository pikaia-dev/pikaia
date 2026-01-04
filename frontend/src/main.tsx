import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StytchB2BProvider } from "@stytch/react/b2b"
import { StytchB2BUIClient } from "@stytch/vanilla-js/b2b"
import { config } from "./lib/env"
import { Toaster } from "./components/ui/sonner"
import App from "./App.tsx"
import "./index.css"

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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <StytchB2BProvider stytch={stytchClient}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
          <Toaster richColors position="top-right" />
        </BrowserRouter>
      </QueryClientProvider>
    </StytchB2BProvider>
  </StrictMode>
)
