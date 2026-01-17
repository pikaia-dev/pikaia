---
trigger: always_on
globs: "frontend/**/*"
---

# Frontend Rules

Coding standards for TypeScript/React frontend.

## Typing & Linting

- TypeScript strict mode; avoid `any`
- Prettier + ESLint (enforced in CI: typecheck + lint + test + build)

## Package Manager

- Use `pnpm` for all Node.js dependency and script commands
- Run scripts with `pnpm run <script>` or `pnpm <script>` (e.g., `pnpm dev`, `pnpm run lint`)
- Never use `npm` or `yarn`
- Add shadcn components with: `pnpm dlx shadcn@latest add <component>`

## API & Data

- One API client module (generated from OpenAPI or typed wrapper); no scattered fetch calls
- Server state: TanStack Query
- Local state: Zustand only if needed; prefer colocation
- Always adhere to the single responsibility principle

## UI & Forms

- shadcn-ui primitives; limit custom CSS
- Forms: React Hook Form + Zod validation

## Auth

- Route guards for auth UX; backend is source of truth

## Security

- No secrets in frontend; only `VITE_*` config

## Performance

- **Algorithm Complexity**:
  - Consider O() complexity when implementing algorithms
  - Prefer optimal solutions where possible, but don't sacrifice readability for minor gains
- **Rendering**:
  - Minimize unnecessary re-renders; use `useMemo`/`useCallback` judiciously (not everywhere)
  - Lazy load routes and heavy components (`React.lazy`, `Suspense`)
  - Virtualize long lists (if >100 items)
- **Loading & Refresh**:
  - Use optimistic updates for snappy UX where appropriate
  - Prefetch data on hover/focus for anticipated navigation
  - Skeleton loaders instead of spinners for content areas
- **Bundle Size**:
  - Tree-shake; avoid importing entire libraries
  - Monitor bundle size in CI (alert on significant increases)

## Testing

- Vitest for lib/API tests
- E2E: TBD (add after core flows stabilize)

## Structure

- `components/` — reusable UI
- `features/` — feature-scoped (components, hooks, queries)
- `lib/` — API client, utilities

### Feature Directory Convention

Each feature in `features/` follows this structure:

- `queries/` — TanStack Query hooks (useQuery wrappers)
- `mutations/` — TanStack mutation hooks (useMutation wrappers)
- `components/` — Feature-specific UI components
- `forms/` — React Hook Form components with Zod schemas
- `types.ts` — Feature-specific TypeScript types
- `api.ts` — API call functions (optional, can reuse lib/api)
