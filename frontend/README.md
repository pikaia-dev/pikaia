# Frontend

React + TypeScript + Vite + shadcn-ui frontend for the SaaS starter.

## Development

```bash
pnpm install      # Install dependencies
pnpm dev          # Start dev server (http://localhost:5173)
pnpm test         # Run tests
pnpm typecheck    # TypeScript check
pnpm lint         # ESLint check
pnpm build        # Production build
```

## API Types

TypeScript types are generated from the backend's OpenAPI spec:

```bash
pnpm generate-types   # Requires backend running at localhost:8000
```

> Run this after any backend API changes to regenerate `src/generated/api-types.ts`.

## Structure

```
src/
├── router.tsx            # Route config with guards
├── main.tsx              # App entry point
├── api/                  # API layer (client, types, hooks)
├── components/ui/        # shadcn-ui components
├── features/             # Feature modules (auth, billing, members, etc.)
├── generated/            # Auto-generated API types (excluded from linting)
├── hooks/                # Shared React hooks
├── layouts/              # Page layouts
├── lib/                  # Utilities, env config, constants
└── pages/                # Route pages

tests/                    # Test files (mirrors src/ structure)
```

## Adding UI Components

```bash
pnpm dlx shadcn@latest add button dialog   # Add shadcn components
```

## Testing

Uses Vitest with React Testing Library:

```bash
pnpm test         # Watch mode
pnpm test run     # Single run
```

Tests are in `tests/` directory, mirroring the `src/` structure.
