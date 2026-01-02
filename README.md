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
cp .env.example .env  # Edit with your API keys
uv sync
uv run python manage.py migrate
uv run python manage.py runserver  # http://localhost:8000

# Frontend (new terminal)
cd frontend
cp .env.example .env  # Edit with your API keys
pnpm install
pnpm dev  # http://localhost:5173
```

### Common Commands

```bash
# Backend
uv run pytest                              # Tests
uv run ruff check . && uv run ruff format . # Lint & format

# Frontend
pnpm dlx shadcn@latest add button dialog   # Add components
```

---

## Third-Party Services

This project requires the following external services. Configure them before running.

| Service | Purpose | Required |
|---------|---------|----------|
| [Stytch](https://stytch.com) | B2B Authentication (magic links, SSO, SCIM) | ✅ Yes |
| [Stripe](https://stripe.com) | Billing & subscriptions | ✅ Yes |
| [Google OAuth](https://console.cloud.google.com) | Google sign-in, coworker suggestions | Optional |
| [Google Places](https://console.cloud.google.com) | Address autocomplete | Optional |

### Stytch Setup

1. Create a **B2B project** at [stytch.com/dashboard](https://stytch.com/dashboard)
2. Add credentials to env files:
   - `backend/.env`: `STYTCH_PROJECT_ID`, `STYTCH_SECRET`
   - `frontend/.env`: `VITE_STYTCH_PUBLIC_TOKEN`

**Dashboard Configuration:**

| Section | Setting | Value |
|---------|---------|-------|
| Redirect URLs | Add URL | `http://localhost:5173/auth/callback` |
| | Enable | Login, Signup, Invite, Discovery |
| Authorized applications | Domains | `localhost` |
| Authentication | Magic Links | ✅ Enabled |
| Organization settings | Create Organizations | ✅ Allow members |
| SDK Configuration | HttpOnly cookies | ❌ Disabled (local dev only) |

> **⚠️ Security:** HttpOnly cookies must be **enabled in production**. Disabling is for local development only.

### Stripe Setup

1. Create account at [stripe.com](https://dashboard.stripe.com)
2. Add credentials to `backend/.env`:
   - `STRIPE_SECRET_KEY` (from Developers → API keys)
   - `STRIPE_WEBHOOK_SECRET` (from webhook setup)
   - `STRIPE_PRICE_ID` (after running `setup_stripe` command)
3. Create products: `uv run python manage.py setup_stripe`

### Google OAuth (Optional)

Enables "Sign in with Google" and coworker suggestions when inviting members.

**Google Cloud Console:**

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. Create **OAuth Client ID** (Web Application)
3. Add authorized redirect URI from Stytch Dashboard (under OAuth → Google)
4. Copy **Client ID** and **Client Secret**

**Stytch Dashboard:**

1. Go to **Authentication** → **OAuth** → **Google**
2. Enable Google and paste the credentials

**For Directory API (coworker suggestions):**

1. In Google Cloud Console → **APIs & Services** → **Enabled APIs**
2. Enable **Admin SDK API**
3. Go to **OAuth consent screen** → **Add or Remove Scopes**
4. Add scope: `https://www.googleapis.com/auth/admin.directory.user.readonly`

> **Note:** Directory API only works for Google Workspace accounts, not personal Gmail.


### Google Places (Optional)

For address autocomplete in billing settings:

1. Enable **Places API** in [Google Cloud Console](https://console.cloud.google.com)
2. Add `VITE_GOOGLE_PLACES_API_KEY` to `frontend/.env`


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

```
User (cross-org identity)
  └── memberships → Member[]
                      └── organization
                      └── role (admin, member)
```

Shared database with organization-scoped data. User/Member models sync from Stytch.

### Key Flows

```
Auth:    Magic Link → Org Picker → JWT → Middleware → API
Billing: Upgrade → Stripe Checkout → Webhook → Subscription Active
Tasks:   Webhook → EventBridge → SQS → Lambda (no Celery/Redis)
```

---

## Project Structure

```
├── backend/              # Django Ninja API
│   ├── apps/
│   │   ├── accounts/     # User, Member, auth flows
│   │   ├── organizations/# Organization model
│   │   ├── billing/      # Stripe integration
│   │   ├── media/        # Image uploads, SVG sanitization
│   │   └── core/         # Security, middleware
│   └── config/settings/  # base.py, local.py, production.py
│
├── frontend/             # Vite + React + shadcn-ui
│   └── src/
│
├── infra/                # AWS CDK (Python)
├── docs/                 # Documentation
└── emails/               # React Email templates
```

---

## Production

Production settings (`config/settings/production.py`) validate required secrets at startup.

```bash
# Required environment variables
export SECRET_KEY="..."
export STYTCH_PROJECT_ID="..." STYTCH_SECRET="..."
export STRIPE_SECRET_KEY="..." STRIPE_WEBHOOK_SECRET="..."
export ALLOWED_HOSTS="api.yourdomain.com"
export CORS_ALLOWED_ORIGINS="https://app.yourdomain.com"
```

---

## Documentation

- [Architecture](./docs/architecture/) — System design, data models
- [Guides](./docs/guides/) — Local development, deployment
- [CONTRIBUTING.md](./CONTRIBUTING.md) — Git workflow, commit format
- [RULES.md](./RULES.md) — Coding standards