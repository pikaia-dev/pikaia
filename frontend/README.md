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

> Run this after any backend API changes to regenerate `src/lib/api-types.ts`.

## Structure

```
src/
├── components/ui/    # shadcn-ui components
├── features/         # Feature modules (queries, mutations, forms, components)
├── hooks/            # Custom React hooks
├── layouts/          # Page layouts
├── lib/              # Utilities, API client, constants
├── pages/            # Route pages
└── test/             # Test setup
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

Tests are co-located with source files (e.g., `schema.test.ts` next to `schema.ts`).
