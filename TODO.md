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

### 2. Missing Stripe Webhook Handler

**File:** `backend/apps/billing/` - no webhook endpoint found

**Issue:** No Stripe webhook handler exists. This means:
- Subscription status changes (cancellations, payment failures) won't be reflected
- Seat count changes from Stripe dashboard won't sync
- Invoice events, disputes, and refunds won't be handled

**Fix:** Implement webhook endpoint at `/api/v1/billing/webhook`:
- Verify webhook signature using `stripe.Webhook.construct_event()`
- Handle key events: `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- Update local Organization billing state accordingly

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

### 4. Billing Info Visible to All Members

**File:** `backend/apps/billing/api.py`

**Issue:** The billing endpoints only check for authenticated member, not admin role. Any member can view:
- Subscription status
- Billing email
- Payment method details

**Fix:** Add admin role check to sensitive billing endpoints:
```python
if not request.member.is_admin:
    return 403, {"detail": "Admin access required"}
```

---

### 5. No Seat Limit Check Before Invite

**File:** `backend/apps/organizations/api.py` - invite endpoint

**Issue:** When inviting new members, there's no check against the subscription seat limit. This allows:
- Inviting more members than paid for
- Potential billing disputes

**Fix:** Before sending invite:
1. Get current member count
2. Get subscription seat limit from Stripe
3. Reject invite if at capacity with helpful error message

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
