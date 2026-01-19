---
trigger: always_on
globs: "frontend/**/*.{ts,tsx},emails/**/*.{ts,tsx}"
paths:
  - "frontend/**/*.{ts,tsx}"
  - "emails/**/*.{ts,tsx}"
---

# Frontend Rules

Coding standards for TypeScript/React frontend.

## Typing & Linting

- TypeScript strict mode; avoid `any`
- Biome for linting and formatting (enforced in CI: typecheck + lint + test + build)
- Run `pnpm run format` to auto-fix formatting issues

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

## File Naming

- Use **kebab-case** for all files (matches shadcn convention)
- Examples: `email-login-form.tsx`, `use-auth-callback.ts`, `bulk-invite-dialog.tsx`
- Component exports remain PascalCase: `export function MembersTable` from `members-table.tsx`

## Imports

- Always use `@/` path alias (configured in `tsconfig.json`)
- Never use relative imports (`../`)
- Same-directory imports (`./`) acceptable for tightly coupled files

**Good:**
```typescript
import { Button } from '@/components/ui/button'
import { useMembers } from '@/features/members/api/queries'
import type { MemberListItem } from '@/api/types'
```

**Bad:**
```typescript
import { Button } from '../../components/ui/button'
```

## No Barrel Re-exports

- Don't create `index.ts` files that only re-export (antipattern)
- Import directly from source files

**Good:**
```typescript
import { MembersTable } from '@/features/members/components/members-table'
import { useDeleteMember } from '@/features/members/api/mutations'
```

**Bad:**
```typescript
import { MembersTable } from '@/features/members/components' // barrel re-export
```

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

- Vitest for unit/integration tests
- Tests in `tests/` directory (mirrors `src/` structure)
- E2E: TBD (add after core flows stabilize)

## Structure

```
frontend/
├── src/
│   ├── app.tsx              # Root component with routes
│   ├── main.tsx             # Entry point
│   │
│   ├── api/                 # API layer (shared across features)
│   │   ├── client.ts        # API client factory
│   │   ├── types.ts         # API response/request types
│   │   ├── use-api.ts       # Authenticated API hook
│   │   └── query-keys.ts    # TanStack Query key factory
│   │
│   ├── components/          # Shared UI components
│   │   └── ui/              # shadcn primitives (button, card, dialog, etc.)
│   │
│   ├── features/            # Feature modules (domain-specific)
│   │   ├── auth/
│   │   ├── billing/
│   │   ├── members/
│   │   ├── organization/
│   │   ├── profile/
│   │   └── webhooks/
│   │
│   ├── generated/           # Auto-generated code (excluded from linting)
│   │   └── api-types.ts     # Generated TypeScript types (if using codegen)
│   │
│   ├── hooks/               # Shared hooks (use-mobile.ts, use-image-upload.ts)
│   │
│   ├── layouts/             # Layout components (app-layout.tsx, app-sidebar.tsx)
│   │
│   ├── lib/                 # Core utilities
│   │   ├── utils.ts         # Shared utilities (cn, etc.)
│   │   ├── env.ts           # Environment config
│   │   └── constants.ts     # App-wide constants
│   │
│   └── pages/               # Page components
│       ├── dashboard.tsx
│       ├── login.tsx
│       └── settings/        # Settings sub-pages
│
└── tests/                   # Test files (mirrors src/ structure)
    ├── setup.ts
    └── features/
        └── auth/
            └── hooks/
                └── use-auth-callback.test.ts
```

### Shared vs Feature-Specific Code

**Shared code** lives at the top level of `src/`:
- `api/` — API client, types, and query infrastructure used by all features
- `components/` — UI components reused across multiple features
- `hooks/` — Utility hooks not tied to a specific domain (e.g., `use-mobile`, `use-sidebar`)
- `lib/` — Pure utilities, config, constants
- `layouts/` — App-wide layout components

**Feature-specific code** lives in `features/{feature}/`:
- Components, hooks, forms, and utilities that belong to one domain
- If code is only used within a single feature, it goes in that feature's directory

### Feature Directory Convention

Each feature in `features/` follows this structure:

```
features/{feature}/
├── api/
│   ├── queries.ts     # TanStack Query hooks (useQuery wrappers)
│   └── mutations.ts   # TanStack mutation hooks (useMutation wrappers)
├── components/        # Feature-specific UI components
├── forms/             # Zod schemas for form validation
├── hooks/             # Feature-specific hooks (if needed)
├── utils/             # Feature-specific utilities
├── types.ts           # Feature-specific TypeScript types
└── constants.ts       # Feature-specific constants
```

**API subdirectory**: Each feature's `api/` folder contains query and mutation hooks that use the shared `@/api/use-api` hook and `@/api/query-keys`.
