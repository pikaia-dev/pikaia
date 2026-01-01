# Authentication

## Overview

Authentication is handled by [Stytch B2B](https://stytch.com/b2b):
- Magic link email authentication
- Organization discovery (multi-org access)
- Role-based access control
- SSO and SCIM ready

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
    Stytch-->>Frontend: IST + Discovered orgs

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
    Backend->>Backend: Validate JWT locally
    Backend->>DB: Sync User/Member/Org
    Backend-->>Frontend: Authenticated response
```

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

**Public Paths:** `/api/v1/auth/magic-link/*`, `/api/v1/health`, `/admin/*`, `/webhooks/stripe/`

## Role-Based Access

Roles synced from Stytch:

| Role | Permissions |
|------|-------------|
| `admin` | Full org management, billing, members |
| `member` | Standard access |
| `viewer` | Read-only |

## Frontend Integration

```typescript
const stytch = useStytchB2BClient();
const { session_jwt } = stytch.session.getTokens();

// Use in API requests
fetch("/api/v1/...", {
  headers: { Authorization: `Bearer ${session_jwt}` },
});
```
