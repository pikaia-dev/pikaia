# Rules

Coding standards for Tango teams and AI agents.

## Python

- Python 3.12+
- Use type hints everywhere; allow `Any` at integration boundaries (ORM, 3rd-party libs) with a comment
- Format with `ruff format`, lint with `ruff check`
- Imports: stdlib → third-party → local (enforced by ruff/isort)

## Comments

- Explain **why**, not what (code should be self-explanatory)
- No commented-out code (use git history)
- No chain-of-thought reasoning in comments

## Django

- Apps live in `apps/` directory
- Models: singular names (`Organization`, not `Organizations`)
- Default: `created_at`, `updated_at` timestamps on all business entities; exceptions allowed with justification
- No raw SQL unless absolutely necessary; if used: parameterized, reviewed, and covered by tests
- Timezones: always store UTC; convert in presentation layer

## API (Django Ninja)

- Routes start at `/api/v1/` (explicit versioning in code preferred over gateway-only)
- Use Pydantic schemas for request/response
- Consistent error format across all endpoints
- Paginate all potentially unbounded lists
    - Default: Cursor pagination (infinite scroll ready)
    - Admin tables: Limit/Offset
    - Small static enumerations: Explicit opt-out allowed

## Testing

- Tests required for all business logic
- Use `pytest` with `pytest-django`
- **Factories** (via `factory_boy`) for all DB models; avoid raw fixtures for data
- Fixtures reserved for external services stubs or static config
- Test file mirrors source: `apps/billing/services.py` → `tests/billing/test_services.py`

## Architecture Boundaries

- Views/routers stay thin
- Orchestration & side effects in services
- Models may contain small domain invariants and helpers; avoid fat models
- External APIs wrapped in dedicated clients (injectable/mockable)
- All outbound HTTP uses same wrapper/defaults (timeouts, retries, backoff); retries only for idempotent requests
- Authorization enforced in service layer (decorators only for coarse-grained checks)

## Naming

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `user_service.py` |
| Classes | PascalCase | `UserService` |
| Functions | snake_case | `get_user_by_id` |
| Constants | SCREAMING_SNAKE | `MAX_RETRY_COUNT` |
| URLs | kebab-case | `/api/v1/user-profiles` |

## Environment

- Use `.env` for local config (never commit)
- All secrets in AWS Secrets Manager for deployed envs (injected as env vars via ECS Task Definition)
- Config via `pydantic-settings`

## Security

- **Non-negotiables in deployed envs**:
    - `DEBUG=False`
    - `SECURE_SSL_REDIRECT=True`
    - `SECURE_HSTS_SECONDS` set (with subdomains)
    - `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`
    - `SECURE_PROXY_SSL_HEADER` configured (behind load balancer)
- **Networking**: Strict CORS policy and `ALLOWED_HOSTS` whitelist
- **Validation**: Strict input validation (Pydantic); file uploads must have size limits and type validation (magic numbers, not just extensions)

## Email

- Templates: React Email (requires build step to compile to HTML assets)
- Sending: Resend API

## Performance

- **Database**:
    - **Avoid N+1**: Use `select_related` (FKs) and `prefetch_related` (M2M/Reverse FKs) by default in services
    - **Indexing**: Add indexes for any field frequently used in `filter()`, `ordering`, or `distinct()`

## Data Consistency & Transactions

- **Transactions**: Use `transaction.atomic()` for multi-write invariants and webhook-driven mutations (not every single `.save()`)
- **External Calls**: Never call external APIs (Stripe, Stytch, Resend) inside a DB transaction
- **Webhooks**: Handlers must be idempotent:
    - Dedupe by event ID (store processed IDs)
    - Side effects must be safe on replay (e.g., don't create duplicate rows/emails)
- **Delivery**: Assume "at-least-once" from EventBridge/SQS
- **Event Publishing**: Use `transaction.on_commit()` to publish events after successful commit

## Frontend

**Typing & Linting**
- TypeScript strict mode; avoid `any`
- Prettier + ESLint (enforced in CI: typecheck + lint + test + build)

**API & Data**
- One API client module (generated from OpenAPI or typed wrapper); no scattered fetch calls
- Server state: TanStack Query
- Local state: Zustand only if needed; prefer colocation

**UI & Forms**
- shadcn-ui primitives; limit custom CSS
- Forms: React Hook Form + Zod validation

**Auth**
- Route guards for auth UX; backend is source of truth

**Security**
- No secrets in frontend; only `VITE_*` config

**Testing**
- Vitest for lib/API tests
- E2E: TBD (add after core flows stabilize)

**Structure**
- `components/` — reusable UI
- `features/` — feature-scoped (components, hooks, queries)
- `lib/` — API client, utilities
