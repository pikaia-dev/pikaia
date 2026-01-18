# Comprehensive CTO Audit Report

**Project:** Tango Django Ninja Stytch SaaS Starter
**Date:** January 2026
**Auditor:** Claude (AI-assisted review)
**Scope:** Full-stack B2B SaaS template evaluation for production readiness

---

## Executive Summary

This template is a **production-quality B2B SaaS foundation** with enterprise-grade features. The codebase demonstrates strong engineering practices with Django Ninja, Stytch B2B authentication, Stripe billing, and AWS CDK infrastructure.

**Overall Assessment: 8.5/10** - Ready for production with targeted improvements.

### Strengths
- Excellent security posture (Stytch B2B, proper secrets management, SVG sanitization)
- Well-architected event system (transactional outbox, webhook delivery)
- Modern frontend stack (React 19, TanStack Query, TypeScript strict mode)
- Comprehensive AWS CDK infrastructure (Aurora Serverless, ECS Fargate, EventBridge)
- Strong typing throughout (Pydantic schemas, TypeScript strict)

### Critical Gaps (Remaining)
1. **Single NAT gateway** (availability risk in production)
2. **No WAF protection** on ALB or CloudFront

### Recently Completed
- ✅ WSGI/ASGI now defaults to production settings
- ✅ HTTPS enforcement via CDK context validation
- ✅ CORS origin validation for production
- ✅ Lambda and EventBridge alarms added
- ✅ 8 Architecture Decision Records documented

### Recommended Priority Actions
1. Add WAF to ALB and CloudFront (High)
2. Add second NAT gateway for production HA (High)
3. Add admin IP whitelist middleware (High)
4. Implement free trial/grace period billing logic (Medium)
5. Add frontend test workflow (Medium)

---

## Table of Contents

1. [Comparison with Industry Templates](#1-comparison-with-industry-templates)
2. [Feature Completeness Analysis](#2-feature-completeness-analysis)
3. [Mobile & Integration Readiness](#3-mobile--integration-readiness)
4. [AWS Infrastructure Audit](#4-aws-infrastructure-audit)
5. [Backend Code Audit](#5-backend-code-audit)
6. [Frontend Code Audit](#6-frontend-code-audit)
7. [Testing & CI/CD Audit](#7-testing--cicd-audit)
8. [Documentation Review](#8-documentation-review)
9. [Prioritized Action Items](#9-prioritized-action-items)

---

## 1. Comparison with Industry Templates

### Reference Projects Analyzed

| Project | Tech Stack | Key Differentiators |
|---------|-----------|---------------------|
| **Apptension SaaS Boilerplate** | Django + GraphQL + React | AI integration, Contentful CMS, Storybook email testing |
| **SaaS Pegasus** | Django + DRF + React/HTMX | Mature, well-documented, teams/billing built-in |
| **Django Ninja (official)** | Django Ninja | Async support, OpenAPI auto-docs, TestClient |

### Feature Comparison

| Feature | Tango Starter | Apptension | SaaS Pegasus |
|---------|---------------|------------|--------------|
| **Auth Provider** | Stytch B2B | Custom OAuth | Custom Django |
| **API Style** | REST (Ninja) | GraphQL | REST (DRF) |
| **Multi-tenancy** | Org-scoped FKs | Similar | Teams model |
| **Billing** | Stripe | Stripe | Stripe |
| **2FA/MFA** | Via Stytch | Built-in UI | Built-in |
| **Passkeys** | ✅ Full WebAuthn | ❌ | ❌ |
| **Event Sourcing** | ✅ Outbox pattern | ❌ | ❌ |
| **Webhooks (outbound)** | ✅ Full system | ❌ | ❌ |
| **AI Integration** | ❌ | ✅ OpenAI | ❌ |
| **CMS Integration** | ❌ | ✅ Contentful | ❌ |
| **Free Trials** | Partial | ✅ | ✅ |
| **Admin Impersonation** | ❌ | ✅ | ✅ |

### Competitive Advantages of Tango Starter

1. **Stytch B2B** - Enterprise SSO, SCIM, RBAC out-of-box (vs building custom)
2. **Passkey/WebAuthn** - Passwordless auth (rare in templates)
3. **Event System** - Production-grade outbox + webhooks (enterprise feature)
4. **AWS-Native** - CDK infrastructure included (most templates are Heroku/Railway)
5. **Phone Verification** - SMS OTP via AWS (compliance-ready)

### Gaps vs Competition

1. **No admin impersonation** for customer support
2. **No AI/LLM integration** boilerplate
3. **No CMS integration** (Contentful, Strapi)
4. **No feature flags** system
5. **Limited email scheduling** (immediate only)

---

## 2. Feature Completeness Analysis

### Essential B2B SaaS Features

| Category | Feature | Status | Notes |
|----------|---------|--------|-------|
| **Auth** | Email/Password | ✅ Via Stytch | Magic links |
| | OAuth (Google) | ✅ | With directory scopes |
| | SSO/SAML | ✅ Via Stytch | Enterprise feature |
| | MFA/2FA | ⚠️ Partial | Stytch supports, no UI |
| | Passkeys | ✅ | Full WebAuthn |
| | Session Management | ✅ | JWT + refresh |
| **Multi-tenancy** | Organizations | ✅ | Stytch-synced |
| | Member Roles | ✅ | admin/member/viewer |
| | Invitations | ✅ | Single + bulk |
| | SCIM Provisioning | ✅ Via Stytch | Enterprise |
| **Billing** | Checkout | ✅ | Stripe Checkout |
| | Subscriptions | ✅ | Per-seat model |
| | Customer Portal | ✅ | Stripe hosted |
| | Invoices | ✅ | List + download |
| | Free Trials | ⚠️ Missing | Need to implement |
| | Grace Periods | ⚠️ Missing | Need to implement |
| | Usage Metering | ❌ | Not implemented |
| **Events** | Event Publishing | ✅ | Transactional outbox |
| | Audit Logs | ✅ | With EventBridge consumer |
| | Webhooks (outbound) | ✅ | Full delivery system |
| | Webhooks (inbound) | ✅ | Stripe + Stytch |
| **Media** | Image Upload | ✅ | S3 + CloudFront |
| | Image Transform | ✅ | Lambda@Edge |
| | SVG Sanitization | ✅ | XXE-safe |
| **Communication** | Transactional Email | ✅ | Resend + React Email |
| | SMS OTP | ✅ | AWS End User Messaging |
| | Push Notifications | ❌ | Not implemented |
| **Admin** | Django Admin | ⚠️ Basic | Exposed, needs hardening |
| | User Impersonation | ❌ | Not implemented |
| | Refunds | ❌ | Stripe dashboard only |
| **Developer** | API Docs | ✅ | Auto OpenAPI |
| | Type Generation | ✅ | Frontend from OpenAPI |
| | Structured Logging | ✅ | Datadog-compatible |

### Recommended Additions Before Branching

**High Priority:**
1. Free trial support with trial_ends_at tracking
2. Grace period handling for failed payments
3. MFA UI components (Stytch supports, needs frontend)
4. Admin IP whitelist or VPN restriction

**Medium Priority:**
5. Feature flags system (LaunchDarkly or custom)
6. Admin impersonation for support
7. Push notification infrastructure (FCM)
8. Rate limiting middleware

**Low Priority:**
9. AI/LLM integration boilerplate
10. CMS integration (Contentful/Strapi)
11. i18n framework setup

---

## 3. Mobile & Integration Readiness

### Current Mobile Support Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| **API Design** | ✅ Good | REST with OpenAPI, versioned |
| **Auth Flow** | ✅ Excellent | Discovery flow, passkeys, mobile provision endpoint |
| **Token Management** | ✅ Good | JWT with refresh via Stytch |
| **Offline Support** | ❌ None | No sync endpoints |
| **Push Notifications** | ❌ None | Not implemented |
| **Deep Linking** | ⚠️ Partial | Magic link redirect configurable |

### Recommendations for Mobile Apps (Pikaia CRM, Time Tracking)

**API Versioning Strategy:**
- Current: URL-based (`/api/v1/`) ✅
- Recommendation: Add `X-API-Version` header for feature flags
- Mobile app compatibility: Maintain v1 for 12+ months after v2 release

**Offline-First Patterns Needed:**

```
Recommended Sync Architecture:
├── POST /api/v1/sync/changes       # Upload local changes
├── GET  /api/v1/sync/pull?since=   # Delta sync with timestamp
├── GET  /api/v1/sync/full          # Full resync fallback
└── Conflict resolution: Last-write-wins or CRDT
```

**Push Notification Infrastructure:**

```
Recommended Stack:
├── Device Token Storage (new model)
│   └── user_id, device_id, fcm_token, platform, created_at
├── AWS SNS or Firebase Admin SDK
├── EventBridge → Lambda → Push
└── Notification Preferences (per-user settings)
```

**CRM Integration Patterns (for Pikaia):**

```
Integration Architecture:
├── Unified Contact Model
│   └── Maps to: Salesforce Contact, HubSpot Contact, etc.
├── OAuth Token Storage
│   └── Per-user, per-integration encrypted tokens
├── Webhook Receivers
│   └── /webhooks/salesforce, /webhooks/hubspot
├── Background Sync Jobs
│   └── Celery/Lambda for bulk operations
└── Rate Limit Handling
    └── Exponential backoff per provider
```

**Time Tracking Features (Toggl Alternative):**

```
Core Models Needed:
├── TimeEntry
│   └── user, project, task, started_at, ended_at, description, billable
├── Project
│   └── organization, client, name, color, billable_rate
├── Timer (ephemeral)
│   └── user, started_at, current_task (for running timers)
└── Report Generation
    └── By project, client, member, date range
```

### API Contract Recommendations

1. **Add `If-Modified-Since` support** for efficient mobile polling
2. **Implement cursor pagination** consistently (already partial)
3. **Add `X-Request-ID` header** pass-through (correlation ID exists)
4. **Document rate limits** in OpenAPI spec
5. **Add webhook retry documentation** for integrators

---

## 4. AWS Infrastructure Audit

### Well-Architected Framework Assessment

| Pillar | Score | Key Findings |
|--------|-------|--------------|
| **Security** | 7/10 | Good encryption, missing WAF, HTTPS not enforced |
| **Reliability** | 7/10 | Multi-AZ DB, single NAT gateway risk |
| **Performance** | 8/10 | Aurora Serverless, CloudFront CDN, RDS Proxy |
| **Cost Optimization** | 8/10 | Serverless-first, PRICE_CLASS_100 |
| **Operational Excellence** | 7/10 | Good dashboards, missing X-Ray tracing |

### Critical Infrastructure Issues

#### 1. ~~HTTPS Not Enforced on API~~ ✅ FIXED
**Status:** CDK now validates `require_https=true` requires `certificate_arn`
**Fix Applied:** `infra/app.py` raises `ValueError` if HTTPS required without certificate

#### 2. Single NAT Gateway (High)
**File:** `infra/stacks/network_stack.py:21`
```python
nat_gateways=1
```
**Risk:** Single point of failure for private subnet egress
**Fix:** Use `nat_gateways=2` for production HA

#### 3. No WAF Protection (High)
**Missing:** AWS WAF on ALB and CloudFront
**Risk:** No OWASP Top 10 protection, no rate limiting at edge
**Fix:** Add WAF WebACL with managed rules

#### 4. ~~CORS Allows All Origins by Default~~ ✅ FIXED
**Status:** CDK now validates CORS origins when `require_https=true`
**Fix Applied:** `infra/app.py` raises `ValueError` if `cors_origins=["*"]` with HTTPS required

#### 5. ALB Origin Uses HTTP Only (Medium)
**File:** `infra/stacks/frontend_stack.py:77-84`
**Risk:** CloudFront → ALB traffic unencrypted
**Fix:** Use HTTPS with proper certificate

### Infrastructure Improvements Checklist

| Item | Priority | Effort | Status |
|------|----------|--------|--------|
| Enforce HTTPS in production | Critical | Low | ✅ Done |
| Restrict CORS origins | High | Low | ✅ Done |
| Add WAF to ALB | High | Medium | ❌ |
| Add WAF to CloudFront | High | Medium | ❌ |
| Add second NAT gateway | High | Low | ❌ |
| Add X-Ray tracing | Medium | Medium | ❌ |
| Add Lambda concurrency limits | Medium | Low | ❌ |
| Add S3 lifecycle policies | Low | Low | ❌ |
| Add cost allocation tags | Low | Low | ❌ |
| Enable GuardDuty | Medium | Low | ❌ |

### Observability Stack Assessment

**Current:**
- ✅ CloudWatch dashboards (4-row layout with key metrics)
- ✅ 7 critical alarms (error rate, latency, CPU, memory, DB)
- ✅ SNS email notifications
- ✅ Structured logging to CloudWatch
- ✅ Lambda alarms (errors, duration, throttling) - *Added*
- ✅ EventBridge delivery metrics and alarms - *Added*

**Missing:**
- ❌ AWS X-Ray distributed tracing
- ❌ RDS Proxy pool exhaustion alarm

---

## 5. Backend Code Audit

### Security Assessment

| Area | Score | Notes |
|------|-------|-------|
| **Authentication** | 9/10 | Stytch JWT validation, proper middleware |
| **Authorization** | 8/10 | Role-based, service-layer enforcement |
| **Input Validation** | 9/10 | Pydantic schemas, SVG sanitization |
| **Secrets Management** | 9/10 | Environment-based, production validation |
| **SQL Injection** | 10/10 | Django ORM, no raw SQL |
| **XSS/XXE** | 9/10 | defusedxml, sanitization |

### Critical Backend Issues

#### 1. ~~WSGI/ASGI Default to Local Settings~~ ✅ FIXED
**Status:** Now defaults to `config.settings.production`
**Fix Applied:** Commit `1acf405` - Changed default in both `wsgi.py` and `asgi.py`

#### 2. Admin Interface Exposed (Medium)
**File:** `backend/config/urls.py`
```python
path("admin/", admin.site.urls)
```
**Risk:** Admin accessible from internet without additional protection
**Fix:** Add IP whitelist middleware or move to separate internal service

### Code Quality Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **Type Hints** | 9/10 | Comprehensive, Pydantic schemas |
| **Code Organization** | 9/10 | Clean app separation, services layer |
| **Error Handling** | 8/10 | Consistent HTTP errors, logging |
| **Logging** | 9/10 | Structlog, correlation IDs |
| **Database Queries** | 8/10 | select_related used, could add more |

### Recommended Backend Improvements

| Item | Priority | Effort | Status |
|------|----------|--------|--------|
| Fix WSGI/ASGI default settings | Critical | 5 min | ✅ Done |
| Add rate limiting middleware | High | 2 hours | ❌ |
| Add admin IP whitelist | High | 1 hour | ❌ |
| Add free trial billing logic | High | 4 hours | ❌ |
| Add admin impersonation | Medium | 4 hours | ❌ |
| Add database read replicas | Medium | 2 hours | ❌ |
| Add feature flags | Medium | 8 hours | ❌ |

---

## 6. Frontend Code Audit

### Overall Assessment: Excellent (9/10)

| Area | Score | Notes |
|------|-------|-------|
| **TypeScript Strictness** | 10/10 | Strict mode, no unused vars |
| **API Client** | 10/10 | Centralized, typed, secure |
| **State Management** | 9/10 | TanStack Query best practices |
| **Forms** | 9/10 | RHF + Zod, comprehensive validation |
| **Performance** | 9/10 | Lazy loading, memoization, caching |
| **Accessibility** | 8/10 | Radix primitives, needs aria-describedby |
| **Bundle Size** | 8/10 | Well-chosen deps, no bundle analysis |

### Frontend Strengths

1. **Query Key Factory Pattern** - Proper cache invalidation
2. **Optimistic Updates** - Profile updates use setQueryData
3. **Code Splitting** - All settings pages lazy-loaded
4. **Form UX** - CSV bulk import, phone number handling
5. **Auth Flow** - Passkey-first for returning users

### Frontend Improvements

| Item | Priority | Effort | Status |
|------|----------|--------|--------|
| Add bundle size monitoring | Medium | 2 hours | ❌ |
| Add aria-describedby for form errors | Medium | 2 hours | ❌ |
| Add E2E tests (Playwright) | Medium | 16 hours | ❌ |
| Add error boundary components | Low | 2 hours | ❌ |
| Add frontend CI workflow | High | 1 hour | ❌ |

*Note: Frontend already has 277 unit tests covering auth, forms, CSV parsing, and utilities.*

---

## 7. Testing & CI/CD Audit

### Test Coverage Summary

**Backend: 37 files, 678 tests, 12,651 lines**

| Area | Files | Tests | Assessment |
|------|-------|-------|------------|
| **accounts** | 6 | 173 | Excellent - API, services, webhooks, models |
| **webhooks** | 6 | 126 | Excellent - Services, signing, REST hooks |
| **core** | 4 | 78 | Good - Security, logging, middleware |
| **billing** | 4 | 76 | Good - Services, webhooks, models |
| **media** | 3 | 71 | Good - Services, SVG sanitizer, API |
| **events** | 8 | 68 | Good - Services, models, cleanup |
| **passkeys** | 3 | 42 | Good - Trusted auth, services, API |
| **sms** | 2 | 27 | Good - Rate limiting, AWS mocking |
| **organizations** | 1 | 17 | Good - Full model coverage (app is models-only) |

**Frontend: 10 files, 277 tests, 1,878 lines**

| Area | Tests | Assessment |
|------|-------|------------|
| **CSV import** | 94 | Excellent - Comprehensive parsing |
| **Auth hooks** | 48 | Excellent - useAuthCallback coverage |
| **Org derivation** | 35 | Good - Domain/slug logic |
| **Countries lib** | 25 | Good - Phone validation |
| **Org API** | 18 | Good - API utilities |
| **Schema validation** | 57 | Good - All forms covered |

### CI/CD Assessment

**Backend CI/CD: ✅ Excellent**

The `test-backend.yml` workflow runs on PRs and pushes to main:
- ✅ PostgreSQL service for integration tests
- ✅ `ruff check` (linting)
- ✅ `ruff format --check` (formatting)
- ✅ `mypy` (type checking - currently `continue-on-error`)
- ✅ `pytest` (tests)
- ✅ `pip-audit` (dependency security scanning)

**Frontend CI/CD: ⚠️ Missing**

No test workflow exists for frontend. Recommend adding:
- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`

### Testing Improvements

| Item | Priority | Effort | Status |
|------|----------|--------|--------|
| Add test workflow to CI | Critical | 2 hours | ✅ Done |
| Add frontend test workflow | High | 1 hour | ❌ |
| Add E2E test framework | Medium | 8 hours | ❌ |
| Add coverage thresholds | Medium | 1 hour | ❌ |
| Add security scanning (bandit) | Medium | 1 hour | ❌ |

---

## 8. Documentation Review

### Current Documentation

| Document | Status | Quality |
|----------|--------|---------|
| `README.md` | ✅ Exists | Good overview |
| `CLAUDE.md` | ✅ Exists | AI assistant context |
| `RULES.md` | ✅ Exists | Coding standards |
| `CONTRIBUTING.md` | ✅ Exists | Git workflow |
| `infra/README.md` | ✅ Exists | CDK deployment |
| `docs/` | ⚠️ Sparse | Needs expansion |
| API docs | ✅ Auto-generated | OpenAPI at /api/docs |

### Missing Documentation

1. ~~**Architecture Decision Records (ADRs)**~~ ✅ Added 8 ADRs in `docs/adr/`
2. **Runbooks** - Deployment, rollback, incident response
3. **API changelog** - Breaking changes between versions
4. **Environment setup guide** - Step-by-step local setup
5. **Testing guide** - How to write tests, mocking patterns
6. **Security guide** - Authentication flows, RBAC model

### Documentation Improvements

| Item | Priority | Effort | Status |
|------|----------|--------|--------|
| Add ADR folder with key decisions | Medium | 4 hours | ✅ Done (8 ADRs) |
| Add deployment runbook | High | 2 hours | ❌ |
| Add local setup guide | High | 2 hours | ❌ |
| Document event types catalog | Medium | 2 hours | ❌ |
| Add API versioning guide | Medium | 1 hour | ❌ |

---

## 9. Prioritized Action Items

### Critical (Do First - Security/Stability)

| # | Item | Effort | Impact | Status |
|---|------|--------|--------|--------|
| 1 | Add test workflow to CI/CD | 2h | Prevents deploying broken code | ✅ Done |
| 2 | Fix WSGI/ASGI default settings | 5m | Prevents DEBUG=True in prod | ✅ Done |
| 3 | Enforce HTTPS in production | 1h | Security compliance | ✅ Done |
| 4 | Restrict CORS origins | 30m | Prevent unauthorized uploads | ✅ Done |

### High Priority (Do This Week)

| # | Item | Effort | Impact |
|---|------|--------|--------|
| 5 | Add WAF to ALB + CloudFront | 4h | OWASP protection |
| 6 | Add second NAT gateway | 30m | Production HA |
| 7 | Add admin IP whitelist | 1h | Admin security |
| 8 | Add rate limiting middleware | 2h | API protection |
| 9 | Add deployment runbook | 2h | Operational safety |

### Medium Priority (Do This Sprint)

| # | Item | Effort | Impact |
|---|------|--------|--------|
| 10 | Implement free trial billing | 4h | Revenue model |
| 11 | Add MFA UI components | 4h | Security feature |
| 12 | Add X-Ray tracing | 2h | Debugging |
| 13 | Add organizations tests | 4h | Test coverage |
| 14 | Add frontend component tests | 8h | Test coverage |
| 15 | Add feature flags system | 8h | Deployment flexibility |

### Low Priority (Backlog)

| # | Item | Effort | Impact |
|---|------|--------|--------|
| 16 | Add admin impersonation | 4h | Support efficiency |
| 17 | Add push notification infra | 8h | Mobile support |
| 18 | Add offline sync endpoints | 16h | Mobile UX |
| 19 | Add AI/LLM boilerplate | 8h | Feature capability |
| 20 | Add CMS integration | 8h | Content management |
| 21 | Add i18n framework | 4h | Internationalization |
| 22 | Add E2E test framework | 16h | Quality assurance |

---

## Appendix A: File-Specific Findings

### Infrastructure Files with Issues

| File | Line | Issue | Severity | Status |
|------|------|-------|----------|--------|
| `infra/stacks/network_stack.py` | 21 | Single NAT gateway | High | ❌ |
| `infra/stacks/app_stack.py` | 317-338 | HTTPS not enforced | Critical | ✅ Fixed |
| `infra/stacks/frontend_stack.py` | 77-84 | ALB origin HTTP only | Medium | ❌ |
| `infra/app.py` | 63 | CORS allows all origins | High | ✅ Fixed |
| `infra/stacks/events_stack.py` | 267 | No Lambda concurrency limit | Medium | ❌ |

### Backend Files with Issues

| File | Line | Issue | Severity | Status |
|------|------|-------|----------|--------|
| `backend/config/wsgi.py` | 1 | Defaults to local settings | Critical | ✅ Fixed |
| `backend/config/asgi.py` | 1 | Defaults to local settings | Critical | ✅ Fixed |
| `backend/config/urls.py` | - | Admin exposed publicly | Medium | ❌ |

---

## Appendix B: Recommended New Files

### 1. `.github/workflows/test-backend.yml` ✅ EXISTS
Backend test pipeline with pytest, ruff, mypy, pip-audit

### 2. `.github/workflows/test-frontend.yml` ❌ TODO
Frontend test pipeline (lint, typecheck, test)

### 3. `docs/adr/` folder ✅ CREATED
Architecture Decision Records (8 ADRs):
- `001-stytch-b2b-authentication.md`
- `002-transactional-outbox-events.md`
- `003-aurora-serverless.md`
- `004-django-ninja.md`
- `005-resend-email.md`
- `006-s3-direct-upload.md`
- `007-soft-deletes-audit-trail.md`
- `008-rds-proxy-connection-pooling.md`

### 4. `docs/runbooks/` ❌ TODO
Operational runbooks:
- `deployment.md`
- `rollback.md`
- `incident-response.md`
- `secrets-rotation.md`

### 5. `backend/apps/core/rate_limiting.py` ❌ TODO
Rate limiting middleware

### 6. `backend/apps/billing/trials.py` ❌ TODO
Free trial logic

---

## Appendix C: Mobile/Integration Architecture

### Recommended Data Models for Pikaia (CRM Extension)

```python
# apps/crm/models.py (new app)

class CRMConnection(TimestampedModel):
    """OAuth connection to external CRM."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50)  # salesforce, hubspot, pipedrive
    access_token_encrypted = models.TextField()
    refresh_token_encrypted = models.TextField()
    token_expires_at = models.DateTimeField()
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

class Contact(TimestampedModel):
    """Unified contact across CRM providers."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=255)  # CRM's ID
    provider = models.CharField(max_length=50)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    last_synced_at = models.DateTimeField()

class Note(TenantScopedModel):
    """User note on a contact."""
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    is_synced_to_crm = models.BooleanField(default=False)

class Task(TenantScopedModel):
    """User task related to a contact."""
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, null=True)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    priority = models.CharField(max_length=20, default='medium')
```

### Recommended Data Models for Time Tracking

```python
# apps/timetracking/models.py (new app)

class Client(TenantScopedModel):
    """Billable client."""
    name = models.CharField(max_length=255)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')

class Project(TenantScopedModel):
    """Project within organization."""
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default='#3B82F6')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    is_billable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

class TimeEntry(TenantScopedModel):
    """Individual time entry."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True)
    description = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True)  # null = running timer
    duration_seconds = models.PositiveIntegerField(null=True)  # computed on stop
    is_billable = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'started_at']),
            models.Index(fields=['organization', 'started_at']),
        ]
```

---

*End of Report*
