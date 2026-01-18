# Roadmap

Future enhancements and improvements planned for Tango.

## Planned

### API Rate Limiting

**Priority:** Medium (implement before significant user traffic)
**Status:** Not started

Protect security-sensitive endpoints from abuse. General API rate limiting can wait until usage patterns are known.

**Current state:**
- SMS OTP endpoints have rate limiting (`OTPRateLimitError`)
- Magic link and other auth endpoints unprotected

**Phase 1 — Pre-launch (security-sensitive endpoints):**

| Endpoint | Limit | Reason |
|----------|-------|--------|
| Magic link send | 5/min per email | Prevents email bombing |
| OTP send | Already implemented | — |
| Password reset | 3/hour per email | Prevents harassment |
| Failed auth | 10/hour per IP+email | Prevents credential stuffing |

Implementation: Simple DB cache counter (already using Django DB cache for passkey challenges).

**Phase 2 — Post-launch (infrastructure-level):**

- Add AWS WAF to ALB with rate-based rule (100 req/5min per IP)
- Blocks bots/scrapers before hitting application
- ~15 lines in CDK, ~$5/month

**Phase 3 — When needed (general API):**

- Measure P95/P99 usage patterns from real users
- Set limits at 10x normal usage
- Only if abuse actually occurs

**Not recommended:**
- Arbitrary limits on regular CRUD operations (hurts legitimate users)
- Rate limiting reads (users pull-to-refresh frequently)

**Reference:**
- [AWS WAF Rate-based Rules](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html)
- [Django Ninja Throttling](https://django-ninja.dev/guides/throttling/)

---

### Admin IP Allowlist

**Priority:** High (security hardening)
**Status:** Not started

Restrict Django admin access to specific IP addresses or VPN ranges.

**Options:**
1. **Middleware-based** — Check `request.META['REMOTE_ADDR']` against allowlist
2. **AWS WAF rule** — IP set condition on `/admin/*` path
3. **CloudFront + Signed URLs** — Separate admin distribution with OAC

**Recommendation:** Start with middleware (simplest), migrate to WAF for production.

**Implementation notes:**
- Store allowed IPs in environment variable or Secrets Manager
- Handle `X-Forwarded-For` header (behind ALB)
- Return 404 (not 403) to avoid confirming admin path exists

---

### Free Trial Support

**Priority:** High (revenue model)
**Status:** Not started

Allow organizations to start with a free trial before requiring payment.

**Data model changes:**
```python
class Organization(Model):
    trial_ends_at = DateTimeField(null=True, blank=True)
    trial_extended_count = IntegerField(default=0)
```

**Implementation:**
1. Set `trial_ends_at` on org creation (e.g., 14 days)
2. Add `is_trial_active` property
3. Grace period handling for trial → paid conversion
4. Email reminders at 7 days, 3 days, 1 day before expiry
5. Feature gating during trial (optional)

**Stripe integration:**
- Create customer without subscription during trial
- Use Stripe Checkout with `trial_period_days` for conversion
- Handle `customer.subscription.trial_will_end` webhook

---

### AWS WAF on ALB

**Priority:** High (security)
**Status:** Not started

Add AWS WAF WebACL to the Application Load Balancer for OWASP protection.

**Managed rule groups to enable:**
- `AWSManagedRulesCommonRuleSet` — OWASP Top 10
- `AWSManagedRulesKnownBadInputsRuleSet` — Log4j, etc.
- `AWSManagedRulesSQLiRuleSet` — SQL injection
- Rate-based rule — 2000 requests per 5 minutes per IP

**CDK implementation:**
```python
from aws_cdk import aws_wafv2 as wafv2

web_acl = wafv2.CfnWebACL(
    self, "WebACL",
    scope="REGIONAL",
    default_action={"allow": {}},
    rules=[
        # Add managed rules here
    ],
)

wafv2.CfnWebACLAssociation(
    self, "WebACLAssociation",
    resource_arn=alb.load_balancer_arn,
    web_acl_arn=web_acl.attr_arn,
)
```

**Cost:** ~$5/month base + $1/million requests
