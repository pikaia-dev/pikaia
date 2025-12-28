# Tango Django Ninja Stytch SaaS Starter

A production-ready B2B SaaS starter built with Django Ninja, Stytch authentication, Stripe billing, and AWS infrastructure.

## Quick Start

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+ with [pnpm](https://pnpm.io/)
- PostgreSQL 16+ (`brew install postgresql@16`)

### Setup

```bash
# Clone and enter
git clone https://github.com/TangoAgency/tango-django-ninja-stytch-saas-starter.git
cd tango-django-ninja-stytch-saas-starter

# PostgreSQL (macOS)
brew services start postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"  # Add to ~/.zshrc
createuser -s postgres 2>/dev/null || true
psql -U postgres -c "ALTER USER postgres PASSWORD 'postgres';"
createdb -U postgres tango

# Backend
cd backend
cp ../.env.example .env  # Edit with your API keys
uv sync
uv run python manage.py migrate
uv run python manage.py runserver  # http://localhost:8000

# Frontend (new terminal)
cd frontend
pnpm install
pnpm dev  # http://localhost:5173
```

### Common Commands

```bash
# Backend (always use uv run)
uv run pytest                      # Tests
uv run ruff check . && uv run ruff format .  # Lint & format

# Frontend
pnpm dlx shadcn@latest add button dialog  # Add components
```

### Third-Party Services

#### Stytch (Authentication)

1. Create a **B2B project** at [stytch.com](https://stytch.com/dashboard)
2. Copy **Project ID** and **Secret** to `backend/.env`
3. Go to **Redirect URLs** → Add `http://localhost:5173/auth/callback`
   - Check **Enabled** for: Login, Signup, Invite, Reset password, Discovery
   - Check **Default** for all (for local dev)
4. Go to **Authentication** → Enable **Magic Links** (minimum for testing)

#### Stripe (Billing)

1. Create account at [stripe.com](https://dashboard.stripe.com)
2. Go to **Developers** → **API keys** → Copy **Secret key** to `backend/.env`
3. Webhook secret: Set up later when implementing billing


---

## Production Configuration

### CORS

In development, `CORS_ALLOW_ALL_ORIGINS = True` permits all cross-origin requests. For production, create `config/settings/production.py`:

```python
from .base import *  # noqa: F403

CORS_ALLOWED_ORIGINS = [
    "https://app.yourdomain.com",
]

# Optional: Allow credentials (cookies, auth headers)
CORS_ALLOW_CREDENTIALS = True
```

---

## Architecture

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 6.0, Django Ninja, PostgreSQL |
| Frontend | Vite, React 19, TypeScript, Tailwind, shadcn-ui |
| Auth | Stytch B2B (magic links, SSO, MFA, SCIM) |
| Billing | Stripe (subscriptions, per-seat, checkout) |
| Infra | AWS CDK, ECS Fargate, Aurora Serverless |

### Multi-Tenancy

- **Shared database** with organization-scoped data
- **Custom User model** synced from Stytch
- **Member model** for org-level roles (admin, member, viewer)

```
User (cross-org identity)
  └── memberships → Member[]
                      └── organization
                      └── role
```

### Authentication Flow

```
Stytch (source of truth)
├── Organizations, Members, Roles
├── SSO/SCIM provisioning
└── Webhooks → Django (sync + extensions)
```

- JWTs validated locally with Stytch public keys
- Org picker for users with multiple memberships

> **Note:** Currently, local User/Member/Organization records sync **inline during auth flows** (login, org creation). Out-of-band changes (e.g., admin edits in Stytch dashboard, SCIM provisioning) require webhook handlers — a future enhancement.

### Billing Flow

```
User signs up → Creates org → Stripe Customer
             → Upgrade → Checkout → Webhook → Subscription active
```

### Background Tasks

```
Webhook → EventBridge → SQS → Lambda
```

No Celery/Redis — fully serverless on AWS.

---

## Project Structure

```
├── backend/              # Django Ninja API
│   ├── apps/
│   │   ├── accounts/     # User, Member models
│   │   ├── organizations/# Organization model
│   │   ├── billing/      # Stripe integration
│   │   └── core/         # Shared base models
│   └── config/settings/  # base.py, local.py, production.py
│
├── frontend/             # Vite + React + shadcn-ui
│   └── src/components/ui/
│
├── infra/                # AWS CDK (Python)
│   └── stacks/
│
└── emails/               # React Email templates
```

**Tooling**: uv (Python), pnpm (Node), ruff (lint/format)

---

## Documentation

- [CONTRIBUTING.md](./CONTRIBUTING.md) — Git workflow, commit format
- [RULES.md](./RULES.md) — Coding standards