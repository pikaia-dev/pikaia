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
