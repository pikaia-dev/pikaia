# Billing & Payments

## Overview

Billing is handled by [Stripe](https://stripe.com) with per-seat subscription pricing:
- In-app payment via Stripe Elements
- Seat-based pricing with automatic quantity sync
- Self-service via Stripe Customer Portal
- Webhook-based state synchronization

## Payment Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Stripe

    User->>Frontend: Click "Upgrade to Pro"
    Frontend->>Backend: Create subscription intent
    Backend->>Stripe: Create incomplete subscription
    Stripe-->>Backend: client_secret + subscription_id
    Backend-->>Frontend: Payment form data
    
    Frontend->>User: Show payment form
    User->>Frontend: Enter card details
    Frontend->>Stripe: Confirm payment
    
    alt Payment Successful
        Stripe-->>Frontend: Success
        Frontend->>Backend: Confirm subscription
        Backend->>Stripe: Retrieve subscription
        Backend-->>Frontend: is_active: true
        Frontend->>User: Show "Pro Plan Active"
    else Payment Failed
        Stripe-->>Frontend: Error
        Frontend->>User: Show error message
    end
```

## Subscription Lifecycle

```mermaid
stateDiagram-v2
    [*] --> None: Org created
    None --> Incomplete: Start upgrade
    Incomplete --> Active: Payment succeeds
    Incomplete --> IncompleteExpired: Payment times out
    Active --> PastDue: Payment fails
    PastDue --> Active: Retry succeeds
    PastDue --> Canceled: Max retries
    Active --> Canceled: User cancels
    Canceled --> [*]
    
    note right of Active: Usable subscription
    note right of PastDue: Grace period
```

## Subscription States

| Status | Usable? | Description |
|--------|---------|-------------|
| `active` | ✅ | Paid and usable |
| `trialing` | ✅ | In trial period |
| `past_due` | ❌ | Payment failed, grace period |
| `canceled` | ❌ | Subscription ended |
| `incomplete` | ❌ | Initial payment pending |

## Seat-Based Pricing

Subscription quantity syncs with organization member count:

```mermaid
flowchart LR
    A[Member added/removed] --> B[Count members]
    B --> C{Quantity changed?}
    C -->|Yes| D[Update Stripe]
    C -->|No| E[Skip]
    D --> F[Prorate billing]
```

**Rules:**
- Quantity updates use proration
- Only syncs for active subscriptions
- Minimum quantity is 1

## Webhook Events

| Event | Action |
|-------|--------|
| `customer.subscription.created` | Create local subscription |
| `customer.subscription.updated` | Update status/quantity |
| `customer.subscription.deleted` | Mark as canceled |
| `invoice.payment_failed` | Log failure |

## Invoice History

Admins can view past invoices directly in the Billing Settings page. Invoices are fetched from Stripe and include:

- Invoice number and status (Paid, Open, etc.)
- Amount and currency
- Date issued
- Links to view online or download PDF

Pagination is supported for organizations with many invoices.

## Development Without Webhooks

The `confirm-subscription` endpoint allows syncing status directly from Stripe, bypassing webhooks for local development.

> **Production:** Always configure webhooks at `/webhooks/stripe/` for reliability.
