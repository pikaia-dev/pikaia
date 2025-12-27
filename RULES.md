# Rules

Coding standards for Tango teams and AI agents.

## Python

- Python 3.12+
- Use type hints everywhere
- Format with `ruff format`, lint with `ruff check`
- Imports: stdlib → third-party → local (enforced by ruff/isort)

## Django

- Apps live in `apps/` directory
- Models: singular names (`Organization`, not `Organizations`)
- Default: `created_at`, `updated_at` timestamps on all business entities; exceptions allowed with justification
- Business logic in services, not views or models
- No raw SQL unless absolutely necessary
- Timezones: always store UTC; convert in presentation layer

## API (Django Ninja)

- Routes start at `/api/` (versioning handled by API Gateway)
- Use Pydantic schemas for request/response
- Consistent error format across all endpoints
- Paginate all potentially unbounded lists; allow explicit opt-out for small static enumerations.

## Testing

- Tests required for all business logic
- Use `pytest` with `pytest-django`
- Factories for flexible object graphs (esp. DB models)
- Fixtures for stable shared setup, heavy objects, or external stubs
- Test file mirrors source: `apps/billing/services.py` → `tests/billing/test_services.py`

## Architecture Boundaries

- Views/routers stay thin
- Orchestration & side effects in services
- Models may contain small domain invariants and helpers; avoid fat models
- External APIs wrapped in dedicated clients. Clients should be injectable/mocked + have retries/timeouts standardized.

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
- All secrets in AWS Secrets Manager for deployed envs
- Config via `pydantic-settings`

## Email

- Templates: React Email
- Sending: Resend API
