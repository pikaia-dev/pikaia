# Tango SaaS Starter

B2B SaaS starter with Django Ninja, Stytch auth, Stripe billing, React frontend.

## Tech Stack

| Layer          | Technology                                 |
| -------------- | ------------------------------------------ |
| Backend        | Python 3.12+, Django 5.x, Django Ninja     |
| Frontend       | React 19, TypeScript, Vite, TanStack Query |
| Auth           | Stytch B2B                                 |
| Billing        | Stripe                                     |
| Database       | PostgreSQL                                 |
| Infrastructure | AWS CDK (ECS Fargate, RDS, S3, CloudFront) |
| Email          | React Email + Resend                       |

## Project Structure

```
.
├── backend/          # Django API (Python, uv)
├── frontend/         # React SPA (TypeScript, pnpm)
├── infra/            # AWS CDK infrastructure
├── emails/           # React Email templates
├── docs/             # Architecture and feature docs
└── scripts/          # Development utilities
```

## Quick Commands

### Backend

```bash
cd backend
uv run python manage.py runserver    # Dev server
uv run pytest                         # Tests
uv run ruff check .                   # Lint
```

### Frontend

```bash
cd frontend
pnpm dev                              # Dev server
pnpm test                             # Tests
pnpm lint                             # Lint
```

### Infrastructure

```bash
cd infra
pnpm cdk deploy --profile tango-b2b-demo
```

## References

- [Contributing Guidelines](../CONTRIBUTING.md)
- [Architecture Docs](../docs/architecture/)
- [Feature Docs](../docs/features/)
