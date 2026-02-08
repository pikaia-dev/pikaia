# Local Development Guide

## Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+ with [pnpm](https://pnpm.io/)
- PostgreSQL 16+

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/pikaia-dev/pikaia.git
cd pikaia
```

### 2. PostgreSQL Setup (macOS)

```bash
brew install postgresql@16
brew services start postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"  # Add to ~/.zshrc

createuser -s postgres 2>/dev/null || true
psql -U postgres -c "ALTER USER postgres PASSWORD 'postgres';"
createdb -U postgres pikaia
```

### 3. Run Setup Script

The interactive setup wizard generates all `.env` files with your configuration:

```bash
./scripts/setup/setup.sh
```

This will prompt for project branding and optionally third-party API keys (Stytch, Stripe, Resend). You can also configure these later:

```bash
./scripts/setup/setup.sh services   # Configure API keys
./scripts/setup/setup.sh aws        # Configure AWS deployment
./scripts/setup/setup.sh status     # View current config
./scripts/setup/setup.sh doctor     # Check for issues
```

> **Prefer manual setup?** Copy `.env.example` to `.env` in both `backend/` and `frontend/` and edit with your values.

### 4. Backend Setup

```bash
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py setup_stripe  # Create Stripe product/price
```

### 5. Frontend Setup

```bash
cd frontend
pnpm install
```

## Running the Application

### Backend (Terminal 1)

```bash
cd backend
uv run python manage.py runserver  # http://localhost:8000
```

### Frontend (Terminal 2)

```bash
cd frontend
pnpm dev  # http://localhost:5173
```

## Environment Variables

### Backend (`backend/.env`)

```env
# Database
DATABASE_URL=postgres://postgres:postgres@localhost:5432/pikaia

# Stytch
STYTCH_PROJECT_ID=project-xxx
STYTCH_SECRET=secret-xxx

# Stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx  # Optional for local dev
STRIPE_PRICE_ID=price_xxx  # Created by setup_stripe

# WebAuthn (Passkeys)
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Pikaia
WEBAUTHN_ORIGIN=http://localhost:5173

# Stytch Trusted Auth Token (for passkey -> Stytch session)
# Create profile at https://stytch.com/dashboard/trusted-auth-tokens
STYTCH_TRUSTED_AUTH_PROFILE_ID=trusted-auth-profile-xxx
STYTCH_TRUSTED_AUTH_AUDIENCE=stytch
STYTCH_TRUSTED_AUTH_ISSUER=passkey-auth
PASSKEY_JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Frontend (`frontend/.env`)

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_STYTCH_PUBLIC_TOKEN=public-token-xxx
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_xxx
```

## Common Commands

### Backend

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=apps

# Lint and format
uv run ruff check . && uv run ruff format .

# Create migration
uv run python manage.py makemigrations

# Apply migrations
uv run python manage.py migrate

# Django shell
uv run python manage.py shell

# Setup Stripe products
uv run python manage.py setup_stripe
```

### Frontend

```bash
# Development server
pnpm dev

# Run tests
pnpm test         # Watch mode
pnpm test run     # Single run

# Regenerate API types from OpenAPI
pnpm generate-types  # Requires backend running

# Type check
pnpm typecheck

# Lint
pnpm lint

# Build for production
pnpm build

# Add shadcn component
pnpm dlx shadcn@latest add button dialog card
```

## Logging

In development, structured logs output as pretty-printed console text with colors. In production, they output as JSON for CloudWatch/Datadog.

```python
from apps.core.logging import get_logger

logger = get_logger(__name__)
logger.info("user_created", user_id="123", email="alice@example.com")
```

All logs automatically include request context (trace ID, user, organization) bound by middleware.

See [Observability Guide](../operations/observability.md) for:
- Field naming conventions (Datadog-compatible)
- Event vs audit log vs structured logging
- CloudWatch Logs Insights queries

## Third-Party Service Setup

### Stytch

1. Create a **B2B project** at [stytch.com](https://stytch.com/dashboard)
2. Copy credentials to `.env` files

**Required Dashboard Settings:**

| Section | Setting | Value |
|---------|---------|-------|
| Redirect URLs | Add URL | `http://localhost:5173/auth/callback` |
| | Enable | Login, Signup, Invite, Discovery |
| Authorized apps | Domains | `localhost` |
| Authentication | Magic Links | ✅ Enabled |
| Organization settings | Create Organizations | ✅ Allow members |
| SDK Configuration | HttpOnly cookies | ❌ **Disabled** (local dev only) |

> **⚠️ Security Note:** Disabling HttpOnly cookies allows JavaScript to read session JWTs, increasing XSS vulnerability impact. This is for **local development only**. In **production**, enable HttpOnly cookies and update auth flows to avoid direct JWT access from JavaScript.

### Stripe

1. Create account at [stripe.com](https://dashboard.stripe.com)
2. Copy **Secret key** to `backend/.env`
3. Copy **Publishable key** to `frontend/.env`
4. Run `uv run python manage.py setup_stripe` to create products

**Webhook Setup (optional for local):**

For local webhook testing:
```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Copy the webhook secret to `STRIPE_WEBHOOK_SECRET` in backend `.env`.

> **Note:** The `confirm-subscription` endpoint allows development without webhooks.

## Troubleshooting

### Database Connection Error

```
psycopg.OperationalError: connection refused
```

**Solution:** Start PostgreSQL:
```bash
brew services start postgresql@16
```

### Stytch JWT Validation Fails

```
HttpError: 401 Unauthorized
```

**Check:**
1. Stytch public token in frontend `.env`
2. Stytch secret in backend `.env`
3. HttpOnly cookies disabled in Stytch dashboard

### Stripe Payment Fails

**Check:**
1. Using test mode keys (start with `sk_test_` / `pk_test_`)
2. Use test card: `4242 4242 4242 4242`
3. Any future expiry date, any CVC

### Module Not Found

```
ModuleNotFoundError: No module named 'apps'
```

**Solution:** Run from the `backend` directory with `uv run`:
```bash
cd backend
uv run python manage.py runserver
```
