# Quick Wins & Action Items

Prioritized improvements from the CTO Audit Report, categorized by effort and impact.

---

## Critical (Do Today) ⚠️

These issues could cause security or stability problems in production.

### 1. Fix WSGI/ASGI Default Settings Module
**Effort:** 5 minutes | **Impact:** Prevents DEBUG=True in production

**Problem:** Both `wsgi.py` and `asgi.py` default to local settings, which means if `DJANGO_SETTINGS_MODULE` isn't set in ECS, the app runs with `DEBUG=True`.

**Files to edit:**
- `backend/config/wsgi.py`
- `backend/config/asgi.py`

**Change:**
```python
# From:
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# To:
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
```

---

## High Priority (Do This Week)

### 2. Restrict CORS Origins in Production
**Effort:** 15 minutes | **Impact:** Prevents unauthorized API/media access

**Problem:** `infra/app.py` defaults CORS to `["*"]` if not specified.

**Fix in `infra/app.py`:**
```python
# Add validation before stack creation
cors_origins = app.node.try_get_context("cors_origins")
if not cors_origins and environment == "production":
    raise ValueError("cors_origins must be specified for production deployment")
```

**Deploy with:**
```bash
cdk deploy --context cors_origins='["https://app.yourdomain.com"]'
```

---

### 3. Add Second NAT Gateway for Production HA
**Effort:** 5 minutes | **Impact:** Eliminates single point of failure

**Edit:** `infra/stacks/network_stack.py`

```python
# Change line 21 from:
nat_gateways=1

# To (for production):
nat_gateways=2  # One per AZ for high availability
```

**Note:** This adds ~$32/month per NAT gateway. Consider using `cdk context` to make this configurable per environment.

---

### 4. Add WAF to ALB
**Effort:** 2 hours | **Impact:** OWASP protection, bot blocking

**Add to `infra/stacks/app_stack.py`:**

```python
from aws_cdk import aws_wafv2 as wafv2

# Create Web ACL
web_acl = wafv2.CfnWebACL(
    self, "ApiWebACL",
    default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
    scope="REGIONAL",
    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
        cloud_watch_metrics_enabled=True,
        metric_name="ApiWebACL",
        sampled_requests_enabled=True,
    ),
    rules=[
        # AWS Managed Rules - Common Rule Set
        wafv2.CfnWebACL.RuleProperty(
            name="AWSManagedRulesCommonRuleSet",
            priority=1,
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS",
                    name="AWSManagedRulesCommonRuleSet",
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="AWSManagedRulesCommonRuleSet",
                sampled_requests_enabled=True,
            ),
        ),
        # Rate limiting
        wafv2.CfnWebACL.RuleProperty(
            name="RateLimitRule",
            priority=2,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    limit=2000,  # requests per 5 minutes per IP
                    aggregate_key_type="IP",
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="RateLimitRule",
                sampled_requests_enabled=True,
            ),
        ),
    ],
)

# Associate with ALB
wafv2.CfnWebACLAssociation(
    self, "ApiWebACLAssociation",
    resource_arn=self.alb.load_balancer_arn,
    web_acl_arn=web_acl.attr_arn,
)
```

---

### 5. Add Admin IP Whitelist
**Effort:** 1 hour | **Impact:** Prevents unauthorized admin access

**Create:** `backend/apps/core/admin_middleware.py`

```python
from django.conf import settings
from django.http import HttpResponseForbidden

class AdminIPWhitelistMiddleware:
    """Restrict /admin/ access to whitelisted IPs."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_ips = getattr(settings, 'ADMIN_ALLOWED_IPS', [])

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            client_ip = self.get_client_ip(request)
            if self.allowed_ips and client_ip not in self.allowed_ips:
                return HttpResponseForbidden("Access denied")
        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
```

**Add to settings:**
```python
# config/settings/production.py
ADMIN_ALLOWED_IPS = parse_comma_list(settings.ADMIN_ALLOWED_IPS)

# Middleware (add before AuthenticationMiddleware)
MIDDLEWARE.insert(3, 'apps.core.admin_middleware.AdminIPWhitelistMiddleware')
```

---

## Medium Priority (Do This Sprint)

### 6. Add Frontend Test Workflow
**Effort:** 15 minutes | **Impact:** Catches frontend bugs before deploy

**Create:** `.github/workflows/test-frontend.yml`

```yaml
name: Test Frontend

on:
  pull_request:
    paths: ['frontend/**']
  push:
    branches: [main]
    paths: ['frontend/**']

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'pnpm'
          cache-dependency-path: frontend/pnpm-lock.yaml
      - name: Install dependencies
        working-directory: frontend
        run: pnpm install
      - name: Lint
        working-directory: frontend
        run: pnpm lint
      - name: Type check
        working-directory: frontend
        run: pnpm run typecheck
      - name: Test
        working-directory: frontend
        run: pnpm test
```

---

### 7. Add Free Trial Support to Billing
**Effort:** 4 hours | **Impact:** Enables standard SaaS trial flow

**Add to `backend/apps/billing/models.py`:**

```python
class Subscription(TimestampedModel):
    # ... existing fields ...

    # Trial support
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_in_trial(self) -> bool:
        if not self.trial_ends_at:
            return False
        return timezone.now() < self.trial_ends_at

    @property
    def trial_days_remaining(self) -> int:
        if not self.is_in_trial:
            return 0
        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days)
```

**Update Stripe checkout to include trial:**
```python
# In billing/services.py create_checkout_session()
checkout_session = stripe.checkout.Session.create(
    # ... existing params ...
    subscription_data={
        "trial_period_days": 14,  # Or from settings
    } if include_trial else None,
)
```

---

### 8. Add X-Ray Tracing to Lambdas
**Effort:** 30 minutes | **Impact:** Better debugging for async flows

**Edit:** `infra/stacks/events_stack.py`

```python
from aws_cdk import aws_lambda as _lambda

# For each Lambda function, add:
tracing=_lambda.Tracing.ACTIVE,
```

**Add IAM permissions:**
```python
event_publisher_fn.add_to_role_policy(
    iam.PolicyStatement(
        actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
        resources=["*"],
    )
)
```

---

## Low Priority (Backlog)

### 9. Add Bundle Size Monitoring
**Effort:** 1 hour

Add `vite-bundle-analyzer` to track frontend bundle size in CI.

### 10. Add Security Scanning (Bandit)
**Effort:** 30 minutes

Add `bandit` to test workflow for Python security scanning.

### 11. Add E2E Tests with Playwright
**Effort:** 8-16 hours

Set up Playwright for critical user flows (login, billing, member invite).

### 12. Add ADR (Architecture Decision Records)
**Effort:** 4 hours

Document key decisions: Why Stytch? Why outbox pattern? Why Aurora Serverless?

---

## Summary by Effort

| Effort | Items |
|--------|-------|
| **< 30 min** | #1 WSGI fix, #3 NAT gateway, #6 Frontend CI |
| **30 min - 2 hours** | #2 CORS, #5 Admin whitelist, #8 X-Ray |
| **2-4 hours** | #4 WAF, #7 Free trials |
| **4+ hours** | #9-12 Backlog items |

---

## Already Done ✅

These items from the original audit are already implemented:

- ✅ **Backend test workflow** - `test-backend.yml` runs pytest, ruff, mypy, and pip-audit
- ✅ **Correlation ID middleware** - Traces requests across services

---

## Verification Checklist

After implementing critical items, verify:

- [ ] `DJANGO_SETTINGS_MODULE` defaults to production
- [x] Tests run on every PR to `main`
- [ ] CORS origins explicitly configured for production
- [ ] WAF attached to ALB (check AWS Console)
- [ ] Admin access restricted to allowed IPs
