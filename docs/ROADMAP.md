# Roadmap

Future enhancements organized by priority and timing.

---

## Do Before Production Launch

Security and stability items that should be addressed before going live with real customers.

### Infrastructure

| Item | Effort | Notes |
|------|--------|-------|
| **Add WAF to ALB** | 2h | OWASP protection, rate limiting at edge |
| **Add WAF to CloudFront** | 2h | Bot protection for static assets |
| **Add second NAT gateway** | 30m | HA for private subnet egress (single point of failure) |
| **ALB origin HTTPS** | 1h | CloudFront → ALB currently HTTP only |

### Backend

| Item | Effort | Notes |
|------|--------|-------|
| **Admin IP allowlist** | 1h | Restrict `/admin/` to VPN/office IPs |
| **Rate limiting (auth endpoints)** | 2h | Magic link, password reset, failed auth |

### Frontend

| Item | Effort | Notes |
|------|--------|-------|
| **Add frontend CI workflow** | 1h | `pnpm lint && pnpm typecheck && pnpm test` |

### Documentation

| Item | Effort | Notes |
|------|--------|-------|
| **Deployment runbook** | 2h | Step-by-step deploy, rollback, secrets rotation |

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
| Free trial support | 4h | When sales model requires it |
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
| Error boundary components | 2h | When unhandled errors affect UX |
| Add aria-describedby for form errors | 2h | When accessibility audit required |
| Coverage thresholds in CI | 1h | When coverage drift becomes a problem |

### Documentation

| Item | Effort | When |
|------|--------|------|
| API versioning guide | 1h | When v2 API is planned |
| Testing guide | 2h | When onboarding new developers |
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

### WAF Configuration

```python
from aws_cdk import aws_wafv2 as wafv2

web_acl = wafv2.CfnWebACL(
    self, "WebACL",
    scope="REGIONAL",
    default_action={"allow": {}},
    rules=[
        # AWSManagedRulesCommonRuleSet — OWASP Top 10
        # AWSManagedRulesKnownBadInputsRuleSet — Log4j, etc.
        # AWSManagedRulesSQLiRuleSet — SQL injection
        # Rate-based rule — 2000 requests per 5 minutes per IP
    ],
)
```

**Cost:** ~$5/month base + $1/million requests

### Admin IP Allowlist

**Options:**
1. **Middleware-based** — Check `request.META['REMOTE_ADDR']` against allowlist
2. **AWS WAF rule** — IP set condition on `/admin/*` path
3. **Separate internal ALB** — Admin on private subnet

**Recommendation:** Start with middleware, migrate to WAF for production.

### Free Trial Implementation

```python
class Organization(Model):
    trial_ends_at = DateTimeField(null=True, blank=True)
    trial_extended_count = IntegerField(default=0)

    @property
    def is_trial_active(self) -> bool:
        if not self.trial_ends_at:
            return False
        return timezone.now() < self.trial_ends_at
```

**Stripe integration:**
- Create customer without subscription during trial
- Use Stripe Checkout with `trial_period_days` for conversion
- Handle `customer.subscription.trial_will_end` webhook

### Rate Limiting (Auth Endpoints)

| Endpoint | Limit | Reason |
|----------|-------|--------|
| Magic link send | 5/min per email | Prevents email bombing |
| Password reset | 3/hour per email | Prevents harassment |
| Failed auth | 10/hour per IP+email | Prevents credential stuffing |

**Implementation:** Simple DB cache counter (already using Django DB cache for passkey challenges).

---

## Completed

Items from the original CTO audit that have been addressed:

- ✅ WSGI/ASGI defaults to production settings
- ✅ HTTPS enforcement via CDK context validation
- ✅ CORS origin validation for production
- ✅ Lambda and EventBridge alarms
- ✅ 8 Architecture Decision Records
- ✅ Thread-safe correlation ID (ContextVar)
- ✅ Webhook idempotency with transaction rollback
- ✅ Bandit security scanning in CI
- ✅ Pre-commit hooks configured
- ✅ Local setup guide (README.md)
- ✅ Event types catalog (webhooks.md)
- ✅ Member list pagination (database-level)
- ✅ IDOR fix (opaque member identifiers)
