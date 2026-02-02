# Pikaia

A production-ready B2B SaaS starter built with Django Ninja, Stytch authentication, Stripe billing, and AWS infrastructure.

## Quick Start

**Prerequisites:** Python 3.12+ ([uv](https://docs.astral.sh/uv/)), Node.js 20+ ([pnpm](https://pnpm.io/)), PostgreSQL 16+

```bash
git clone https://github.com/pikaia-dev/pikaia.git
cd pikaia

# Backend
cd backend && cp .env.example .env  # Add your API keys
uv sync && uv run python manage.py migrate
uv run python manage.py runserver   # http://localhost:8000

# Frontend (new terminal)
cd frontend && cp .env.example .env
pnpm install && pnpm dev            # http://localhost:5173
```

> **First time?** See the [Local Development Guide](./docs/guides/local-development.md) for PostgreSQL setup, environment variables, third-party service configuration, and troubleshooting.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 6.0, Django Ninja, PostgreSQL |
| Frontend | Vite, React 19, TypeScript, Tailwind, shadcn-ui |
| Auth | Stytch B2B (magic links, passkeys, SSO, SCIM) |
| Billing | Stripe (subscriptions, per-seat pricing) |
| Infra | AWS CDK, ECS Fargate, Aurora Serverless |

## Architecture

```
User (cross-org identity)
  └── memberships → Member[]
                      └── organization
                      └── role (admin, member)
```

Shared database with organization-scoped data. User/Member/Organization models sync from Stytch.

**Key Flows:**
```
Auth:    Magic Link → Org Picker → JWT → Middleware → API
Billing: Upgrade → Stripe Checkout → Webhook → Subscription Active
Events:  Domain Event → EventBridge → SQS → Lambda
```

## Project Structure

```
├── backend/              # Django Ninja API
│   ├── apps/             # accounts, organizations, billing, media, core
│   └── config/settings/  # base.py, local.py, production.py
├── frontend/             # Vite + React + shadcn-ui
├── infra/                # AWS CDK (Python)
├── docs/                 # Documentation
└── emails/               # React Email templates
```

## Documentation

- **[Local Development](./docs/guides/local-development.md)** — Setup, environment variables, third-party services
- **[Architecture](./docs/architecture/)** — System design, data models, events
- **[Features](./docs/features/)** — Auth, billing, organizations, media uploads
- **[Production Deployment](./docs/guides/production-deployment.md)** — AWS CDK deployment
- **[Testing](./docs/guides/testing.md)** — Test strategy and commands
- **[Contributing](./CONTRIBUTING.md)** — Git workflow, commit format
- **[Coding Standards](./.agent/rules/)** — Backend and frontend conventions
