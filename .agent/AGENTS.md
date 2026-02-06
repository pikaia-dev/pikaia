# Pikaia

B2B SaaS starter with Django Ninja, Stytch auth, Stripe billing, React frontend.

## Quick Reference

**Package managers:** `uv` (Python), `pnpm` (Node.js) — never use pip/npm/yarn directly

**Run commands:**
- Backend: `uv run pytest`, `uv run python manage.py ...`
- Frontend: `pnpm dev`, `pnpm test`, `pnpm dlx shadcn@latest add <component>`

**File naming:**
- Python: `snake_case.py`
- Frontend: `kebab-case.tsx`

**Key principles:**
- Stytch = auth source of truth, Stripe = billing source of truth
- Thin controllers, rich services
- External API calls outside DB transactions
- Type hints everywhere (Python + TypeScript strict)

## Detailed Standards

- [Backend Rules](./rules/backend/coding-standards.md) — Python/Django conventions
- [Frontend Rules](./rules/frontend/coding-standards.md) — TypeScript/React conventions
- [Global Conventions](./rules/_global/conventions.md) — Shared standards

## Project Documentation

- [Contributing Guidelines](../CONTRIBUTING.md)
- [Architecture Docs](../docs/architecture/)
- [Feature Docs](../docs/features/)
