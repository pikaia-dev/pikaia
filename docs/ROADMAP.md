# Roadmap

Future enhancements and improvements planned for Tango.

## Planned

### API Rate Limiting

**Priority:** High
**Status:** Not started

Implement general API rate limiting to protect against abuse and DoS attacks.

**Current state:**
- Only SMS OTP endpoints have rate limiting (`OTPRateLimitError`)
- No protection on other API endpoints

**Recommended approach:**
- Use [django-ratelimit](https://django-ratelimit.readthedocs.io/) or implement custom middleware
- Apply sensible defaults per endpoint category:
  - Authentication endpoints: 5 requests/minute per IP
  - Write operations: 30 requests/minute per user
  - Read operations: 100 requests/minute per user
- Return `429 Too Many Requests` with `Retry-After` header
- Consider Redis backend for distributed rate limiting in production

**Reference:**
- [OWASP Rate Limiting Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Rate_Limiting_Cheat_Sheet.html)
- [Django Ninja Throttling](https://django-ninja.dev/guides/throttling/)
