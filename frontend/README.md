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

TypeScript types are manually maintained in `src/api/types.ts` to match the Django Ninja API schemas.
Update that file when backend API contracts change.

## Structure

```
src/
├── router.tsx            # Route config with guards
├── main.tsx              # App entry point
├── api/                  # API layer (client, types, hooks)
├── components/ui/        # shadcn-ui components
├── features/             # Feature modules (auth, billing, members, etc.)
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
