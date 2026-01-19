/**
 * Centralized query key factory for TanStack Query.
 *
 * Pattern: Each feature has an `all` key for broad invalidation,
 * and specific keys for individual queries.
 *
 * @see https://tkdodo.eu/blog/effective-react-query-keys
 */
export const queryKeys = {
  auth: {
    all: ['auth'] as const,
    me: () => [...queryKeys.auth.all, 'me'] as const,
  },
  organization: {
    all: ['organization'] as const,
    detail: () => [...queryKeys.organization.all, 'detail'] as const,
  },
  members: {
    all: ['members'] as const,
    list: () => [...queryKeys.members.all, 'list'] as const,
  },
  billing: {
    all: ['billing'] as const,
    subscription: () => [...queryKeys.billing.all, 'subscription'] as const,
    invoices: (params?: { limit?: number; starting_after?: string }) =>
      [...queryKeys.billing.all, 'invoices', params] as const,
  },
  webhooks: {
    all: ['webhooks'] as const,
    events: () => [...queryKeys.webhooks.all, 'events'] as const,
    endpoints: () => [...queryKeys.webhooks.all, 'endpoints'] as const,
    endpoint: (id: string) => [...queryKeys.webhooks.all, 'endpoint', id] as const,
    deliveries: (endpointId: string) =>
      [...queryKeys.webhooks.all, 'deliveries', endpointId] as const,
  },
} as const
