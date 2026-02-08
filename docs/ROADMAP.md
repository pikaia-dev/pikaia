# Roadmap

Future enhancements organized by priority and timing.

---

## Do Before Production Launch

Security and stability items that should be addressed before going live with real customers.

### Infrastructure

| Item | Effort | Notes |
|------|--------|-------|
| ~~**Add WAF to ALB**~~ | ~~2h~~ | Done — `infra/stacks/waf_stack.py` (WafRegionalStack) |
| ~~**Add WAF to CloudFront**~~ | ~~2h~~ | Done — `infra/stacks/waf_stack.py` (WafCloudFrontStack) |
| **Add second NAT gateway** | 30m | HA for private subnet egress (single point of failure) |
| ~~**ALB origin HTTPS**~~ | ~~1h~~ | Done — CloudFront → ALB via HTTPS with origin verification header |

### Backend

| Item | Effort | Notes |
|------|--------|-------|
| **Admin IP allowlist** | 1h | Restrict `/admin/` to VPN/office IPs |
| ~~**Rate limiting (auth endpoints)**~~ | ~~2h~~ | Done — atomic cache counters on magic link, password reset, failed auth |

### Frontend

| Item | Effort | Notes |
|------|--------|-------|
| ~~**Add frontend CI workflow**~~ | ~~1h~~ | Done — `.github/workflows/test-frontend.yml` (lint, format, typecheck, test) |

### Documentation

| Item | Effort | Notes |
|------|--------|-------|
| **Deployment runbook** | 2h | Step-by-step deploy, rollback, secrets rotation |
| ~~**scripts/setup-client.sh**~~ | ~~1h~~ | Done — see `scripts/setup/setup.sh` (interactive setup wizard via `@clack/prompts`) |

---

## Do After Launch (When Needed)

Items that become important as the product scales or based on customer feedback.

### Infrastructure — Observability & Cost

| Item | Effort | When |
|------|--------|------|
| Add X-Ray tracing | 2h | When debugging distributed issues |
| Add Lambda concurrency limits | 30m | When Lambda costs spike |
| Add S3 lifecycle policies | 1h | When storage costs grow |
| Add cost allocation tags | 1h | When cost attribution needed |
| Enable GuardDuty | 30m | For compliance requirements |
| Add RDS Proxy pool exhaustion alarm | 30m | When connection issues arise |

### Backend — Features

| Item | Effort | When |
|------|--------|------|
| ~~Free trial support~~ | ~~4h~~ | Done — trial fields on Organization, Stripe checkout with `trial_period_days` |
| Grace period for failed payments | 2h | When churn from failed cards is an issue |
| MFA UI components | 4h | When enterprise customers require it |
| Admin impersonation | 4h | When support volume increases |
| Feature flags system | 8h | When A/B testing or gradual rollouts needed |
| Database read replicas | 2h | When read load exceeds primary capacity |
| General API rate limiting | 4h | When abuse patterns emerge (measure first) |

### Frontend — Quality

| Item | Effort | When |
|------|--------|------|
| E2E tests (Playwright) | 16h | When regression bugs become costly |
| Bundle size monitoring | 2h | When load times become an issue |
| ~~Error boundary components~~ | ~~2h~~ | Done — `error-fallback.tsx` with router and app-level boundaries |
| Add aria-describedby for form errors | 2h | When accessibility audit required |
| Coverage thresholds in CI | 1h | When coverage drift becomes a problem |

### Documentation

| Item | Effort | When |
|------|--------|------|
| API versioning guide | 1h | When v2 API is planned |
| Security guide | 2h | For compliance documentation |

---

## Future Capabilities (Backlog)

Nice-to-have features that expand the platform's capabilities.

### Mobile & Integration

| Item | Effort | Notes |
|------|--------|-------|
| Push notification infrastructure | 8h | FCM/APNs via SNS |
| Offline sync endpoints | 16h | For mobile-first apps |
| CRM integration boilerplate | 8h | Salesforce, HubSpot connectors |

### Platform

| Item | Effort | Notes |
|------|--------|-------|
| AI/LLM integration boilerplate | 8h | OpenAI/Anthropic patterns |
| CMS integration | 8h | Contentful or Strapi |
| i18n framework | 4h | Frontend + backend translation |
| Usage metering for billing | 8h | Beyond seat-based pricing |

---

## Reference Implementation Details

### Admin IP Allowlist

**Options:**
1. **Middleware-based** — Check `request.META['REMOTE_ADDR']` against allowlist
2. **AWS WAF rule** — IP set condition on `/admin/*` path
3. **Separate internal ALB** — Admin on private subnet

**Recommendation:** Start with middleware, migrate to WAF for production.
