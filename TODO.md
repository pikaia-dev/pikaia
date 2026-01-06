# TODO - Codebase Review Findings

Last reviewed: 2026-01-06

---

## HIGH Priority

### 1. SSRF Vulnerability in Avatar Proxy

**File:** `backend/apps/accounts/api.py` (around line 98)

**Issue:** The avatar proxy endpoint fetches arbitrary URLs without validation. An attacker could use this to:
- Probe internal network services (169.254.169.254 for AWS metadata, internal IPs)
- Exfiltrate data via DNS/HTTP requests
- Bypass firewalls by using the server as a proxy

**Fix:** Add URL validation:
- Allowlist of domains (e.g., only allow known avatar providers like Gravatar, Google, GitHub)
- Block private IP ranges and localhost
- Consider using a dedicated image proxy service

---

### ~~2. Missing Stripe Webhook Handler~~ ✅ ALREADY IMPLEMENTED

**File:** `backend/apps/billing/webhooks.py`

Already implemented at `/webhooks/stripe/` with:
- Signature verification via `stripe.Webhook.construct_event()`
- Handlers for: `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.paid/payment_failed`
- Comprehensive test coverage in `tests/billing/test_webhooks.py`

---

## MEDIUM Priority

### 3. Stytch-to-Local Sync Can Diverge

**Files:**
- `backend/apps/stytch_utils/member_sync.py`
- `backend/apps/organizations/api.py`

**Issue:** When creating/updating members, the code:
1. Creates in Stytch
2. Creates locally in Django

If step 2 fails, Stytch has the member but Django doesn't. There's no reconciliation mechanism.

**Fix options:**
- Wrap in transaction and implement Stytch rollback on local failure
- Add periodic sync job to reconcile Stytch ↔ Django state
- Use Stytch webhooks as source of truth

---

### ~~4. Billing Info Visible to All Members~~ ✅ ALREADY IMPLEMENTED

**File:** `backend/apps/billing/api.py`

Already properly secured:
- All sensitive endpoints (`create_checkout`, `create_portal`, `list_invoices`, etc.) have `@require_admin`
- Only `get_subscription` is available to all members (intentional - needed for feature gating)

---

### ~~5. No Seat Limit Check Before Invite~~ ❌ NOT AN ISSUE

**File:** `backend/apps/billing/services.py`

The billing is per-seat with automatic scaling, NOT capped seats:
- `sync_subscription_quantity()` automatically updates subscription when members are added/removed
- Stripe charges based on actual member count via proration
- No seat limit enforcement needed - billing just scales automatically

---

## LOW Priority

### 6. Stytch Auth on Every Request

**File:** `backend/apps/stytch_utils/middleware.py`

**Issue:** Every authenticated request calls Stytch's `sessions.authenticate()` API. This adds latency and increases Stytch API usage costs.

**Fix options:**
- Cache session validity locally (with short TTL, e.g., 60 seconds)
- Trust JWT signature verification without round-trip (Stytch JWTs are signed)
- Only re-authenticate on sensitive operations

---

### 7. No Pagination on Member List

**File:** `backend/apps/organizations/api.py` - member list endpoint

**Issue:** Member list returns all members without pagination. For large organizations, this could:
- Cause slow responses
- Memory issues on server
- Poor UX on frontend

**Fix:** Add offset/limit pagination:
```python
@router.get("/members", response=PaginatedMemberList)
def list_members(request, offset: int = 0, limit: int = 50):
    members = Member.objects.filter(organization=request.organization)[offset:offset+limit]
    ...
```

---

## Notes

- The codebase is generally well-structured with clear separation of concerns
- Stytch B2B integration is comprehensive (magic links, OAuth, passkeys)
- Multi-tenancy model (User → Member → Organization) is sound
- Frontend uses modern patterns (TanStack Query, proper TypeScript)
