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
import { useMembers } from '@/features/members/queries'
```

**Bad:**
```typescript
import { Button } from '../../components/ui/button'
```

## No Barrel Re-exports

- Don't create `index.ts` files that only re-export (antipattern)
- `queries/index.ts` and `mutations/index.ts` are fine — they contain actual hook code
- Import directly from source files

**Good:**
```typescript
import { MembersTable } from '@/features/members/components/members-table'
import { useDeleteMember } from '@/features/members/mutations'
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
│   │   ├── api-schema.json  # OpenAPI schema
│   │   └── api-types.ts     # Generated TypeScript types
│   │
│   ├── hooks/               # Global hooks (use-api.ts, use-image-upload.ts)
│   │
│   ├── layouts/             # Layout components (app-layout.tsx, app-sidebar.tsx)
│   │
│   ├── lib/                 # Core utilities
│   │   ├── api.ts           # API client
│   │   ├── utils.ts         # Shared utilities (cn, etc.)
│   │   └── env.ts           # Environment config
│   │
│   ├── pages/               # Page components
│   │   ├── dashboard.tsx
│   │   ├── login.tsx
│   │   └── settings/        # Settings sub-pages
│   │
│   └── shared/              # Cross-feature shared code
│       ├── query-keys.ts    # TanStack Query keys
│       └── types.ts         # Shared types
│
└── tests/                   # Test files (mirrors src/ structure)
    ├── setup.ts
    └── features/
        └── auth/
            └── hooks/
                └── use-auth-callback.test.ts
```

### Feature Directory Convention

Each feature in `features/` follows this structure:

- `queries/index.ts` — TanStack Query hooks (useQuery wrappers)
- `mutations/index.ts` — TanStack mutation hooks (useMutation wrappers)
- `components/` — Feature-specific UI components (one file per component)
- `forms/` — React Hook Form components with Zod schemas
- `utils/` — Feature-specific utilities
- `hooks/` — Feature-specific hooks (if needed)
- `types.ts` — Feature-specific TypeScript types
- `constants.ts` — Feature-specific constants
