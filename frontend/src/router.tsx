import { useStytchMember, useStytchMemberSession } from '@stytch/react/b2b'
import { useEffect, useState } from 'react'
import {
  type ActionFunction,
  createBrowserRouter,
  isRouteErrorResponse,
  type LoaderFunction,
  Navigate,
  Outlet,
  type RouteObject,
  type ShouldRevalidateFunction,
  useRouteError,
} from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { SettingsSkeleton } from '@/components/ui/skeleton'
import AppLayout from '@/layouts/app-layout'
import { STYTCH_ROLES } from '@/lib/constants'

// ============ Types ============

type GuardComponent = React.ComponentType<{ children: React.ReactNode }>

interface AppRouteConfig {
  // Route matching (passed directly to React Router)
  path?: string
  index?: boolean
  caseSensitive?: boolean
  id?: string

  // Components
  lazy?: () => Promise<{ default: React.ComponentType }>
  fallback?: React.ComponentType
  errorElement?: React.ReactNode

  // Data functions
  loader?: LoaderFunction
  action?: ActionFunction
  shouldRevalidate?: ShouldRevalidateFunction

  // Structure
  children?: AppRouteConfig[]
  redirectTo?: string

  // Guards & Layout (our extensions)
  guards?: GuardComponent[]
  layout?: React.ComponentType

  // Custom metadata (breadcrumbs, titles, permissions, etc.)
  handle?: Record<string, unknown>
}

// ============ Fallbacks ============

function GlobalFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <LoadingSpinner />
    </div>
  )
}

function SettingsFallback() {
  return <SettingsSkeleton />
}

// ============ Route Error Boundary ============

function RootErrorBoundary() {
  const error = useRouteError()

  let message = 'An unexpected error occurred. Please try again.'
  if (isRouteErrorResponse(error)) {
    message = error.statusText || `${String(error.status)} error`
  } else if (import.meta.env.DEV && error instanceof Error) {
    message = error.message
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4 max-w-md px-4">
        <h1 className="text-4xl font-bold">Something went wrong</h1>
        <p className="text-muted-foreground">{message}</p>
        <Button onClick={() => window.location.replace('/')}>Try again</Button>
      </div>
    </div>
  )
}

// ============ Guards ============

function ProtectedRoute({ children }: { children?: React.ReactNode }) {
  const { session, isInitialized } = useStytchMemberSession()
  const [waitingTimedOut, setWaitingTimedOut] = useState(false)

  // Check if we should wait for session (set during login flow)
  const justLoggedIn = sessionStorage.getItem('stytch_just_logged_in') === 'true'

  // Clear flag when session arrives
  useEffect(() => {
    if (session && justLoggedIn) {
      sessionStorage.removeItem('stytch_just_logged_in')
    }
  }, [session, justLoggedIn])

  // Timeout safety valve - only runs when waiting for session
  useEffect(() => {
    if (!justLoggedIn || session || waitingTimedOut) return

    const timer = setTimeout(() => {
      sessionStorage.removeItem('stytch_just_logged_in')
      setWaitingTimedOut(true)
    }, 5000)
    return () => {
      clearTimeout(timer)
    }
  }, [justLoggedIn, session, waitingTimedOut])

  const isWaitingForSession = justLoggedIn && !session && !waitingTimedOut

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- isInitialized can be false during SDK init
  if (!isInitialized || isWaitingForSession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <LoadingSpinner className="mx-auto" />
          {isWaitingForSession && (
            <p className="mt-4 text-sm text-muted-foreground">Signing you in...</p>
          )}
        </div>
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  return <>{children ?? <Outlet />}</>
}

function AdminRoute({ children }: { children?: React.ReactNode }) {
  const { member, isInitialized } = useStytchMember()

  // Wait for Stytch member data to load before checking roles
  if (!isInitialized || !member) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>
    )
  }

  const roles = member.roles || []
  const isAdmin = roles.some((r: { role_id?: string }) => r.role_id === STYTCH_ROLES.ADMIN)

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children ?? <Outlet />}</>
}

// ============ Routes Config ============

const routes: AppRouteConfig[] = [
  {
    errorElement: <RootErrorBoundary />,
    children: [
      // Public routes
      { path: '/login', lazy: () => import('@/pages/login') },
      { path: '/auth/callback', lazy: () => import('@/pages/auth-callback') },

      // Protected routes
      {
        guards: [ProtectedRoute],
        layout: AppLayout,
        children: [
          { path: '/', redirectTo: '/dashboard' },
          { path: '/dashboard', lazy: () => import('@/pages/dashboard') },
          { path: '/settings', redirectTo: '/settings/profile' },
          {
            path: '/settings/profile',
            lazy: () => import('@/pages/settings/profile-settings'),
            fallback: SettingsFallback,
          },
          {
            path: '/settings/organization',
            lazy: () => import('@/pages/settings/organization-settings'),
            fallback: SettingsFallback,
            guards: [AdminRoute],
          },
          {
            path: '/settings/members',
            lazy: () => import('@/pages/settings/members-settings'),
            fallback: SettingsFallback,
            guards: [AdminRoute],
          },
          {
            path: '/settings/billing',
            lazy: () => import('@/pages/settings/billing-settings'),
            fallback: SettingsFallback,
            guards: [AdminRoute],
          },
          {
            path: '/settings/security',
            lazy: () => import('@/pages/settings/security-settings'),
            fallback: SettingsFallback,
            guards: [AdminRoute],
          },
          {
            path: '/settings/integrations',
            lazy: () => import('@/pages/settings/integrations-settings'),
            fallback: SettingsFallback,
            guards: [AdminRoute],
          },
        ],
      },

      { path: '*', lazy: () => import('@/pages/not-found') },
    ],
  },
]

// ============ Route Builder ============

function composeGuards(guards: GuardComponent[], children: React.ReactNode): React.ReactNode {
  // biome-ignore lint/correctness/useJsxKeyInIterable: guards are nested wrappers, not sibling list items
  return guards.reduceRight<React.ReactNode>((acc, Guard) => <Guard>{acc}</Guard>, children)
}

function buildRoutes(configs: AppRouteConfig[]): RouteObject[] {
  return configs.map((config) => {
    // Handle redirects
    if (config.redirectTo) {
      return { path: config.path, element: <Navigate to={config.redirectTo} replace /> }
    }

    // Build route object with all supported properties
    const route: RouteObject = {
      path: config.path,
      index: config.index,
      id: config.id,
      caseSensitive: config.caseSensitive,
      errorElement: config.errorElement,
      loader: config.loader,
      action: config.action,
      shouldRevalidate: config.shouldRevalidate,
      handle: config.handle,
    }

    // Add lazy loading with HydrateFallback
    if (config.lazy) {
      const lazyLoader = config.lazy
      const Fallback = config.fallback ?? GlobalFallback
      const guards = config.guards

      // Guards on leaf routes (no children) - wrap the lazy component
      if (!config.children && guards?.length) {
        route.lazy = async () => {
          const module = await lazyLoader()
          const Component = module.default
          const GuardedComponent = () => composeGuards(guards, <Component />) as React.ReactElement
          return {
            Component: GuardedComponent,
            HydrateFallback: Fallback,
          }
        }
      } else {
        route.lazy = async () => {
          const module = await lazyLoader()
          return {
            Component: module.default,
            HydrateFallback: Fallback,
          }
        }
      }
    }

    // Process children with guards and layout
    if (config.children) {
      const Layout = config.layout
      // biome-ignore lint/correctness/useJsxKeyInIterable: conditional render, not list iteration
      const layoutElement = Layout ? <Layout /> : <Outlet />

      if (config.guards?.length) {
        route.element = composeGuards(config.guards, layoutElement)
      } else if (Layout) {
        route.element = layoutElement
      }

      route.children = buildRoutes(config.children)
    }

    return route
  })
}

export const router = createBrowserRouter(buildRoutes(routes))
