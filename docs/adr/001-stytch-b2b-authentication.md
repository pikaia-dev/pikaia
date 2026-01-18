# ADR 001: Stytch B2B for Authentication

**Date:** January 18, 2026

## Context

We need an authentication system for a B2B SaaS product that supports:
- Multi-tenant organizations with member management
- Enterprise requirements (SSO, SCIM, RBAC)
- Modern passwordless options (magic links, passkeys)
- Minimal custom auth code to maintain

Options considered:
1. **Custom Django auth** - Full control, significant development/maintenance
2. **Auth0** - Mature, but B2B features require enterprise tier
3. **Clerk** - Developer-friendly, but primarily B2C focused
4. **Stytch B2B** - Purpose-built for B2B multi-tenant applications

## Decision

Use **Stytch B2B** as the primary authentication provider.

## Rationale

### B2B-First Architecture
Stytch B2B is designed around the organization-member model we need:
- Organizations are first-class entities (not bolted on)
- Members belong to organizations with roles
- Built-in RBAC (admin, member, viewer roles)
- SCIM provisioning for enterprise customers
- SSO/SAML per organization

### Enterprise Features Out of Box
Without building anything custom:
- Google Workspace / Microsoft Entra SSO
- SAML 2.0 for enterprise IdPs
- SCIM for automated user provisioning
- Organization-level MFA policies
- Session management and device tracking

### Passwordless-Forward
Aligns with modern security best practices:
- Magic links as primary auth method
- WebAuthn/passkeys supported via Trusted Auth
- SMS OTP for phone verification
- OAuth (Google, Microsoft) with proper scopes

### Reduced Development Burden
We don't build or maintain:
- Password hashing, reset flows, breach detection
- Session token generation and validation
- SSO/SAML integration complexity
- SCIM endpoint implementation
- MFA enrollment and verification

### Webhook-Driven Sync
Stytch webhooks keep our local database in sync:
- `organization.created`, `organization.updated`
- `member.created`, `member.updated`, `member.deleted`
- Enables offline access to user data for queries

## Consequences

### Positive
- **Faster time to market** - Auth is handled, focus on product
- **Enterprise-ready from day one** - SSO/SCIM without custom work
- **Security maintained by experts** - Auth is hard to get right
- **Scales with us** - Same provider from startup to enterprise

### Negative
- **Vendor dependency** - Auth is a critical path, tied to Stytch
- **Cost at scale** - Per-MAU pricing adds up with growth
- **Limited customization** - Must work within Stytch's model
- **Network dependency** - Auth requires Stytch API availability

### Mitigations
- Local user/member/org tables provide query independence
- JWT validation can be done locally (no API call per request)
- Webhook sync ensures local data is current
- Could migrate to custom auth if economics require (tables are ours)

## Implementation Notes

### Local Data Model
```
User (cross-org identity)
  └── email, name, avatar (synced from Stytch)

Organization (tenant)
  └── stytch_org_id, name, slug (synced from Stytch)

Member (org-scoped)
  └── stytch_member_id, user, organization, role (synced from Stytch)
```

### Auth Flow
1. Frontend initiates auth via Stytch SDK
2. Stytch handles magic link/OAuth/SSO
3. Frontend receives session JWT
4. Backend validates JWT (local verification or Stytch API)
5. Middleware populates `request.auth_user`, `request.auth_member`, `request.auth_organization`

### Passkey Integration
Stytch's "Trusted Auth" allows us to:
1. Verify passkey locally (WebAuthn)
2. Exchange verified credential for Stytch session
3. User gets full Stytch session without Stytch handling WebAuthn
