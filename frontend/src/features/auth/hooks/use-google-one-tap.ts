import { useStytchB2BClient } from '@stytch/react/b2b'
import { useCallback, useEffect, useRef, useState } from 'react'

interface OneTapState {
  isAvailable: boolean
  isLoading: boolean
  error: string | null
  didRender: boolean
  notRenderedReason: string | null
}

interface UseGoogleOneTapOptions {
  /** Auto-show One Tap on mount. Defaults to true. */
  autoShow?: boolean
  /** Redirect URL after One Tap auth. Defaults to /auth/callback */
  redirectUrl?: string
}

interface UseGoogleOneTapReturn {
  state: OneTapState
  showOneTap: () => Promise<void>
}

/**
 * Hook for Google One Tap authentication in discovery flow.
 *
 * Shows the browser-native Google prompt in the top-right corner.
 * Falls back gracefully if One Tap can't render (e.g., user dismissed it,
 * third-party cookies blocked, etc.)
 */
export function useGoogleOneTap(options: UseGoogleOneTapOptions = {}): UseGoogleOneTapReturn {
  const { autoShow = true, redirectUrl } = options
  const stytch = useStytchB2BClient()
  const hasAutoShown = useRef(false)

  const [state, setState] = useState<OneTapState>({
    isAvailable: true,
    isLoading: false,
    error: null,
    didRender: false,
    notRenderedReason: null,
  })

  const showOneTap = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }))

    try {
      const result = await stytch.oauth.googleOneTap.discovery.start({
        discovery_redirect_url: redirectUrl ?? `${window.location.origin}/auth/callback`,
      })

      setState((prev) => ({
        ...prev,
        isLoading: false,
        didRender: result.isPromptDisplayed,
        notRenderedReason: result.isPromptDisplayed ? null : (result.reason ?? 'Unknown reason'),
        isAvailable: result.isPromptDisplayed,
      }))
    } catch (err) {
      // One Tap not available (e.g., not configured, test environment)
      const message = err instanceof Error ? err.message : 'Google One Tap not available'
      setState((prev) => ({
        ...prev,
        isLoading: false,
        isAvailable: false,
        error: message,
      }))
    }
  }, [stytch, redirectUrl])

  // Auto-show on mount if enabled
  useEffect(() => {
    if (autoShow && !hasAutoShown.current) {
      hasAutoShown.current = true
      void showOneTap()
    }
  }, [autoShow, showOneTap])

  return { state, showOneTap }
}
