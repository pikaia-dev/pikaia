# Tango Django Ninja Stytch SaaS Starter

A production-ready B2B SaaS starter template built with Django Ninja, Stytch B2B authentication, Stripe billing, and AWS infrastructure.

## Architecture Decisions

### Multi-Tenancy

- **Approach**: Shared database with tenant ID columns (organization-scoped data)
- **Terminology**: "Organization" (aligned with Stytch B2B naming)
- **Future consideration**: Can evolve to schema-per-tenant or database-per-tenant if needed

### Authentication (Stytch B2B)

- Magic links
- Password-based auth
- SSO (Google, Microsoft, SAML)
- MFA
- SCIM provisioning

**Key Design Decisions:**

- **Organization creation**: Self-service (users sign up → create org → invite members)
- **RBAC approach**: Hybrid
  - Stytch handles org-level roles (`admin`, `member`, `viewer`)
  - Django handles entity-level permissions (project access, resource sharing)
- **Source of truth**: Stytch for org/member data, synced to Django via webhooks
- **Session handling**: JWTs (stateless, short expiry + refresh tokens)
  - Better for multi-platform (web, mobile, desktop, API access)
  - Validate locally with Stytch public keys

**Data Flow:**
```
Stytch (source of truth)
├── Organizations, Members, Org-level Roles
├── SSO/SCIM provisioning
└── Webhook sync → Django (read replica + extensions)
                   └── Entity-level permissions
                   └── App-specific data
```

### Frontend

| Component | Technology |
|-----------|------------|
| Bundler | Vite |
| Styling | Tailwind CSS |
| Components | shadcn-ui |
| Architecture | Separate SPA |

**Key Design Decisions:**

- Django Ninja serves as a pure API backend
- Frontend is a separate application (independent deployments)
- API-first approach enables web, mobile, desktop, and API access to use the same backend

### Billing (Stripe)

- Per-seat pricing (default plan, extensible)
- Subscription plans (monthly & annual with price difference)
- Credits system via Stripe Customer Balance
- Customer Portal (Stripe-hosted billing management)
- Webhooks for payment events and subscription changes
- Stripe Checkout (easy migration to Elements later)

**Payment Flow:**
```
1. User signs up → Stytch
2. Creates org → Django + Stripe Customer created
3. Upgrade → Stripe Checkout → Webhook → Subscription activated
```

### AWS Infrastructure

| Component | Technology |
|-----------|------------|
| Compute | ECS Fargate |
| Database | Aurora Serverless v2 PostgreSQL |
| Infrastructure as Code | AWS CDK (Python) |

**Multi-Region Strategy:**

- Starter deploys to **single region**
- Users have a `region` field for future geo-routing
- Clear documentation for multi-region expansion:
  - Add Aurora read replicas in other regions
  - Or separate Aurora clusters per region for full data residency
  - Route 53 geolocation routing

### AWS Services

| Service | Purpose |
|---------|---------|
| S3 | File uploads, static assets |
| CloudFront | CDN for frontend |
| SQS | Message queue |
| EventBridge | Event routing (webhooks, async) |
| Lambda | Background task processing |
| Secrets Manager | API keys, credentials |
| CloudWatch | Logs, metrics, alerts |

**No Redis/ElastiCache** - using EventBridge + SQS + Lambda instead of Celery.

### Email

| Type | Provider |
|------|----------|
| Auth emails (magic links, OTPs) | Stytch (built-in) |
| Billing emails (receipts, invoices) | Stripe (built-in) |
| App emails (welcome, notifications) | **Resend** (default) |

- Resend chosen for better DX, managed deliverability, and no ops burden
- SES documented as alternative for cost optimization at scale
- Email abstracted behind `EmailProvider` interface for swappability

### Background Task Architecture

```
External webhook (Stripe, Stytch)
        │
        ▼
   EventBridge  ──→  Routes by event type
        │
        ├──→ SQS queue ──→ Lambda consumer
        └──→ Direct Lambda (simple cases)
```

No Celery, no Redis - fully AWS-native, serverless background processing.

## Project Structure

```
tango-django-ninja-stytch-saas-starter/
├── backend/                      # Django project
│   ├── apps/                     # Domain apps
│   │   ├── accounts/             # User/Member sync, profiles
│   │   ├── billing/              # Stripe integration
│   │   ├── organizations/        # Multi-tenancy
│   │   └── core/                 # Shared models, utils
│   ├── config/                   # Django settings & root config
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── local.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── api.py                # Django Ninja root
│   │   └── wsgi.py / asgi.py
│   ├── tests/                    # Mirrors apps/ structure
│   ├── manage.py
│   ├── pyproject.toml            # uv
│   └── Dockerfile
│
├── frontend/                     # Vite + React + TypeScript
│   ├── src/
│   │   ├── components/           # Reusable UI (shadcn-ui)
│   │   ├── features/             # Feature modules
│   │   ├── lib/                  # API client, utils
│   │   ├── layouts/
│   │   └── pages/
│   ├── package.json
│   └── Dockerfile
│
├── infra/                        # AWS CDK (Python)
│   ├── app.py
│   ├── stacks/
│   └── constructs/
│
├── emails/                       # React Email templates
│   └── src/templates/
│
├── docker-compose.yml            # Local dev
├── pnpm-workspace.yaml
└── .env.example
```

**Tooling**: uv (Python), pnpm (Node), ruff (linting)

## Getting Started

See [GETTING_STARTED.md](./GETTING_STARTED.md) for detailed setup instructions.