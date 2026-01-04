---
trigger: always_on
globs: *.py
---

# Backend Rules

Coding standards for Python/Django backend. Scoped to `*.py` files.

## Python

- Python 3.12+
- Use type hints everywhere; allow `Any` at integration boundaries (ORM, 3rd-party libs) with a comment
- Format with `ruff format`, lint with `ruff check`
- Imports: stdlib → third-party → local (enforced by ruff/isort)

## Package Manager

- Use `uv` for all Python dependency and command management
- Run commands with `uv run <command>` (e.g., `uv run pytest`, `uv run python manage.py migrate`)
- Never use `pip`, `python`, or `pip install` directly
- Virtual environment is managed by uv at `backend/.venv`

## Django

- Apps live in `apps/` directory
- Models: singular names (`Organization`, not `Organizations`)
- Default: `created_at`, `updated_at` timestamps on all business entities; exceptions allowed with justification
- No raw SQL unless absolutely necessary; if used: parameterized, reviewed, and covered by tests
- Timezones: always store UTC; convert in presentation layer

## API (Django Ninja)

- Routes start at `/api/v1/` (explicit versioning in code)
- Use Pydantic schemas for request/response
- Consistent error format across all endpoints
- Paginate all potentially unbounded lists
    - Default: Cursor pagination (infinite scroll ready)
    - Admin tables: Limit/Offset
    - Small static enumerations: Explicit opt-out allowed

## Testing

- Always run tests when making changes and make sure relevant tests are not skipped.
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

## Performance

- **Algorithm Complexity**:
    - Consider O() complexity when implementing algorithms
    - Prefer optimal solutions where possible, but don't sacrifice readability for minor gains
    - Document non-obvious performance trade-offs in comments
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