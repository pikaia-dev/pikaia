# Rules

Coding standards for Tango teams and AI agents.

## Comments

- Explain **why**, not what (code should be self-explanatory)
- No commented-out code (use git history)
- No chain-of-thought reasoning in comments

## Naming

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `user_service.py` |
| Classes | PascalCase | `UserService` |
| Functions | snake_case | `get_user_by_id` |
| Constants | SCREAMING_SNAKE | `MAX_RETRY_COUNT` |
| URLs | kebab-case | `/api/v1/user-profiles` |
| Unused vars | _prefix | `_unused_fixture` |

## Testing

- Prefix variables that exist only to create DB state with `_` (e.g., `_existing_member = MemberFactory(...)`)
- This silences linter warnings and signals intentional non-use

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
