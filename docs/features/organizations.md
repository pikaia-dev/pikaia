# Organizations & Multi-Tenancy

## Overview

The system implements **shared database multi-tenancy** where all organizations share the same database, with data isolation through foreign key relationships.

## Multi-Tenancy Model

```mermaid
graph TB
    subgraph "Shared Database"
        U1[User: alice@example.com]
        U2[User: bob@example.com]

        O1[Organization: Acme Corp]
        O2[Organization: Beta Inc]

        M1[Member: Alice @ Acme]
        M2[Member: Alice @ Beta]
        M3[Member: Bob @ Acme]

        U1 --> M1
        U1 --> M2
        U2 --> M3

        M1 --> O1
        M2 --> O2
        M3 --> O1
    end
```

## User Multi-Org Access

A single user (identified by email) can be a member of multiple organizations with different roles:

```mermaid
flowchart LR
    subgraph User
        email["alice@example.com"]
    end

    subgraph Memberships
        M1[Admin @ Acme Corp]
        M2[Member @ Beta Inc]
        M3[Viewer @ Gamma LLC]
    end

    email --> M1
    email --> M2
    email --> M3
```

## Organization Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created: User creates org
    Created --> Active: Org is usable
    Active --> Upgraded: User upgrades
    Upgraded --> Active: Subscription ends
    Active --> [*]: Org deleted

    note right of Created: User creates org via Stytch
    note right of Active: Free tier
    note right of Upgraded: Paid subscription
```

## Data Isolation

All queries are scoped to the authenticated member's organization:

```python
def get_resources(org: Organization):
    return Resource.objects.filter(organization=org)
```

## Stytch Sync

Organization data syncs from Stytch:

| Stytch Field | Django Field |
|--------------|--------------|
| `organization_id` | `stytch_org_id` |
| `organization_name` | `name` |
| `organization_slug` | `slug` |

**Local Extensions** (not in Stytch):
- Billing address and VAT info
- Stripe customer ID
- App-specific settings
