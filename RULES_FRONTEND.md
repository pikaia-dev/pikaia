# Frontend Rules

Coding standards for TypeScript/React frontend. Scoped to `*.ts`, `*.tsx` files.

## Typing & Linting

- TypeScript strict mode; avoid `any`
- Prettier + ESLint (enforced in CI: typecheck + lint + test + build)

## API & Data

- One API client module (generated from OpenAPI or typed wrapper); no scattered fetch calls
- Server state: TanStack Query
- Local state: Zustand only if needed; prefer colocation

## UI & Forms

- shadcn-ui primitives; limit custom CSS
- Forms: React Hook Form + Zod validation

## Auth

- Route guards for auth UX; backend is source of truth

## Security

- No secrets in frontend; only `VITE_*` config

## Testing

- Vitest for lib/API tests
- E2E: TBD (add after core flows stabilize)

## Structure

- `components/` — reusable UI
- `features/` — feature-scoped (components, hooks, queries)
- `lib/` — API client, utilities
