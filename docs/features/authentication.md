# Authentication

## Overview

Authentication is handled by [Stytch B2B](https://stytch.com/b2b) with native WebAuthn passkey support:
- **Passkeys (WebAuthn)** — Passwordless biometric authentication
- Magic link email authentication
- Google OAuth sign-in
- Organization discovery (multi-org access)
- Role-based access control
- SSO and SCIM ready

> **Mobile Apps:** For mobile-specific auth (silent provisioning, phone OTP), see [Mobile Authentication](./mobile-authentication.md).

## Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Stytch
    participant Backend
    participant DB

    User->>Frontend: Enter email
    Frontend->>Stytch: Send magic link
    Stytch->>User: Email with link
    User->>Frontend: Click link
    Frontend->>Stytch: Authenticate token
    Stytch-->>Frontend: IST (Intermediate Session Token) + Discovered orgs

    alt User has existing orgs
        Frontend->>User: Show org picker
        User->>Frontend: Select org
        Frontend->>Stytch: Exchange IST for session
    else No existing orgs
        Frontend->>User: Show create org form
        User->>Frontend: Submit org details
        Frontend->>Stytch: Create org + exchange IST
    end

    Stytch-->>Frontend: Session JWT
    Frontend->>Backend: API request + JWT
    Backend->>Stytch: Validate JWT + get roles
    Stytch-->>Backend: Member/roles
    Backend->>DB: Sync User/Member/Org
    Backend-->>Frontend: Authenticated response
```

> **Note:** JWT validation uses Stytch API (not local JWKS) to ensure role changes reflect immediately.

## Key Concepts

| Term | Description |
|------|-------------|
| **IST** | Intermediate Session Token — temporary token before org selection |
| **Session JWT** | Full authentication token after org selection |
| **Discovery** | Finding all orgs a user can access |
| **Exchange** | Converting IST to session by selecting an org |

## JWT Middleware Flow

```mermaid
flowchart TD
    A[Request arrives] --> B{Public path?}
    B -->|Yes| C[Skip auth]
    B -->|No| D{Has JWT?}
    D -->|No| E[Unauthenticated]
    D -->|Yes| F[Validate JWT]
    F -->|Invalid| E
    F -->|Valid| G{Member exists?}
    G -->|Yes| H[Load from DB]
    G -->|No| I[JIT Sync from Stytch]
    H --> J[Attach to request]
    I --> J
```

**Public Paths:** `/api/v1/auth/magic-link/*`, `/api/v1/health`, `/admin/*`, `/webhooks/stripe/`, `/webhooks/stytch/`

## Role-Based Access

Roles synced from Stytch:

| Role | Permissions |
|------|-------------|
| `admin` | Full org management, billing, members |
| `member` | Standard access |
| `viewer` | Read-only (planned, not yet enforced by backend) |

## Frontend Integration

```typescript
const stytch = useStytchB2BClient();
const { session_jwt } = stytch.session.getTokens();

// Use in API requests
fetch("/api/v1/...", {
  headers: { Authorization: `Bearer ${session_jwt}` },
});
```

## Webhooks

Stytch webhooks provide real-time synchronization when changes occur outside authentication:

| Event | Action |
|-------|--------|
| `*.member.update` | Sync role changes, status updates |
| `*.member.delete` | Soft delete local member |
| `*.organization.update` | Sync name, slug, logo changes |

### Setup

1. Configure webhook endpoint in Stytch Dashboard: `https://yourapp.com/webhooks/stytch/`
2. Copy the signing secret to `STYTCH_WEBHOOK_SECRET` environment variable
3. Enable events: `member.update`, `member.delete`, `organization.update`

> **Note:** Webhooks use Svix for delivery with automatic retries and signature verification.

## Passkeys (WebAuthn)

Native WebAuthn passkey support for passwordless biometric authentication (Face ID, Touch ID, Windows Hello).

### Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Authenticator

    User->>Frontend: Click "Sign in with Passkey"
    Frontend->>Backend: POST /auth/passkeys/authenticate/options
    Backend-->>Frontend: challenge + options
    Frontend->>Authenticator: navigator.credentials.get()
    Authenticator-->>Frontend: Signed credential
    Frontend->>Backend: POST /auth/passkeys/authenticate/verify
    Backend-->>Frontend: Session tokens
```

### API Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /auth/passkeys/register/options` | Required | Get registration options |
| `POST /auth/passkeys/register/verify` | Required | Complete registration |
| `POST /auth/passkeys/authenticate/options` | Public | Get authentication options |
| `POST /auth/passkeys/authenticate/verify` | Public | Verify and create session |
| `GET /auth/passkeys` | Required | List user's passkeys |
| `DELETE /auth/passkeys/{id}` | Required | Delete a passkey |

### Configuration

Backend environment variables:

```env
# WebAuthn Core Settings
WEBAUTHN_RP_ID=localhost          # Your domain (no protocol/port)
WEBAUTHN_RP_NAME=Your App         # Display name in browser prompts
WEBAUTHN_ORIGIN=http://localhost:5173  # Full origin URL

# Stytch Trusted Auth Token (converts passkey auth → real Stytch session)
STYTCH_TRUSTED_AUTH_PROFILE_ID=trusted-token-profile-xxx
STYTCH_TRUSTED_AUTH_AUDIENCE=stytch
STYTCH_TRUSTED_AUTH_ISSUER=passkey-auth
PASSKEY_JWT_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----'
```

> **Production:** Set `WEBAUTHN_RP_ID` to your domain (e.g., `app.example.com`) and `WEBAUTHN_ORIGIN` to your full HTTPS URL.

### Stytch Trusted Auth Token Setup

Passkey authentication uses Stytch's [Trusted Auth Tokens](https://stytch.com/docs/b2b/sessions/attest) to exchange a verified passkey credential for a **real Stytch B2B session**, enabling full RBAC and session management.

#### 1. Generate RSA Key Pair

```bash
# Generate private key
openssl genpkey -algorithm RSA -out passkey-private.pem -pkeyopt rsa_keygen_bits:2048

# Extract public key (PEM format for Stytch dashboard)
openssl rsa -pubout -in passkey-private.pem -out passkey-public.pem
```

#### 2. Configure Stytch Dashboard

1. Go to [Stytch Dashboard → Trusted Auth Tokens](https://stytch.com/dashboard/trusted-auth-tokens)
2. Create a new profile:
   - **Name:** `Passkey Authentication`
   - **Audience:** `stytch`
   - **Issuer:** `passkey-auth`
3. Under **Public Keys**, paste the contents of `passkey-public.pem`
4. Under **Required Attributes**, map:
   - `email` (JWT claim) → `email` (Stytch attribute)
   - `sub` (JWT claim) → `token_id` (Stytch attribute)
5. Save and copy the **Profile ID** (starts with `trusted-token-profile-`)

#### 3. Add Environment Variables

```env
STYTCH_TRUSTED_AUTH_PROFILE_ID=trusted-token-profile-xxx-yyy-zzz
PASSKEY_JWT_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----'
```

> **Note:** Format the private key with `\n` for newlines and wrap in single quotes.

### Session Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Stytch

    User->>Frontend: Biometric auth (Face ID, Touch ID)
    Frontend->>Backend: POST /auth/passkeys/authenticate/verify
    Backend->>Backend: Verify WebAuthn signature
    Backend->>Backend: Create signed JWT with user claims
    Backend->>Stytch: sessions.attest(trusted_token)
    Stytch-->>Backend: Real session_token + session_jwt
    Backend-->>Frontend: Session tokens
    Frontend->>Frontend: Store session, redirect to app
```

### Browser Support

Passkeys work in modern browsers with biometric hardware:
- ✅ Chrome/Edge 108+ (Windows Hello, Android)
- ✅ Safari 16+ (Touch ID, Face ID)
- ✅ Firefox 122+ (experimental)

The frontend gracefully degrades when passkeys aren't supported.

## Google OAuth

Optional Google sign-in alongside magic links.

### Setup

**Google Cloud Console:**

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. Create **OAuth Client ID** (Web Application)
3. Add authorized redirect URI from Stytch Dashboard (under OAuth → Google)
4. Set OAuth consent screen **User type** to **External** (or Internal for Workspace-only)

**Stytch Dashboard:**

1. Go to **Authentication** → **OAuth** → **Google**
2. Enable Google and paste Client ID + Secret

### Directory API (Coworker Suggestions)

When inviting members, suggestions from the user's Google Workspace directory can appear.

**Additional Setup:**

1. Enable **Admin SDK API** in Google Cloud Console
2. Add OAuth scope: `https://www.googleapis.com/auth/admin.directory.user.readonly`
3. Users must re-authenticate to grant the new scope

> **Note:** Only works for Google Workspace accounts. Personal Gmail users see no suggestions (graceful degradation).
