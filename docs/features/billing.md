# Billing & Payments

## Overview

Billing is handled by [Stripe](https://stripe.com) with per-seat subscription pricing. The system supports:
- Subscription upgrades with in-app payment (Stripe Elements)
- Seat-based pricing with automatic quantity sync
- Customer billing portal for self-service
- Webhook-based state synchronization

## Payment Flow

### Upgrade Flow (Stripe Elements)

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Stripe

    User->>Frontend: Click "Upgrade to Pro"
    Frontend->>Backend: POST /billing/subscription-intent
    Backend->>Stripe: Create subscription (incomplete)
    Note over Backend,Stripe: billing_mode: flexible<br/>payment_behavior: default_incomplete
    Stripe-->>Backend: Subscription + confirmation_secret
    Backend-->>Frontend: client_secret, subscription_id
    
    Frontend->>User: Show PaymentElement form
    User->>Frontend: Enter card details
    Frontend->>Stripe: stripe.confirmPayment()
    Stripe->>Stripe: Process payment
    
    alt Payment Successful
        Stripe-->>Frontend: Success
        Frontend->>Backend: POST /billing/confirm-subscription
        Backend->>Stripe: Retrieve subscription
        Stripe-->>Backend: status: active
        Backend->>Backend: Sync to database
        Backend-->>Frontend: is_active: true
        Frontend->>User: Show "Pro Plan Active"
    else Payment Failed
        Stripe-->>Frontend: Error
        Frontend->>User: Show error message
    end
```

### Subscription Lifecycle

```mermaid
stateDiagram-v2
    [*] --> None: Org created
    None --> Incomplete: Create subscription intent
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

| Status | `is_active` | Description |
|--------|-------------|-------------|
| `active` | ✅ | Paid and usable |
| `trialing` | ✅ | In trial period |
| `past_due` | ❌ | Payment failed, grace period |
| `canceled` | ❌ | Subscription ended |
| `incomplete` | ❌ | Initial payment pending |
| `incomplete_expired` | ❌ | Initial payment failed |
| `unpaid` | ❌ | Multiple payment failures |
| `paused` | ❌ | Temporarily paused |

## API Endpoints

### Get Subscription
```
GET /api/v1/billing/subscription
```
Returns current subscription status.

**Requires:** Valid session JWT

**Response (subscribed):**
```json
{
  "status": "active",
  "quantity": 5,
  "current_period_end": "2024-02-01T00:00:00Z",
  "cancel_at_period_end": false
}
```

**Response (free tier):**
```json
{
  "status": "none",
  "quantity": 3,
  "current_period_end": null,
  "cancel_at_period_end": false
}
```

### Create Subscription Intent
```
POST /api/v1/billing/subscription-intent
```
Creates a subscription for in-app payment with Stripe Elements.

**Requires:** Admin role

**Request:**
```json
{
  "quantity": 5
}
```

**Response:**
```json
{
  "client_secret": "pi_xxx_secret_xxx",
  "subscription_id": "sub_xxx"
}
```

### Confirm Subscription
```
POST /api/v1/billing/confirm-subscription
```
Syncs subscription status from Stripe after payment. Useful for development without webhooks.

**Requires:** Admin role

**Request:**
```json
{
  "subscription_id": "sub_xxx"
}
```

**Response:**
```json
{
  "is_active": true
}
```

### Create Checkout Session
```
POST /api/v1/billing/checkout
```
Creates a Stripe Checkout session (redirect-based flow).

**Requires:** Admin role

**Request:**
```json
{
  "success_url": "https://app.example.com/billing?success=true",
  "cancel_url": "https://app.example.com/billing",
  "quantity": 5
}
```

### Create Portal Session
```
POST /api/v1/billing/portal
```
Creates a Stripe Customer Portal session for self-service billing management.

**Requires:** Admin role, existing subscription

**Request:**
```json
{
  "return_url": "https://app.example.com/billing"
}
```

## Webhook Events

The system handles these Stripe webhook events:

| Event | Handler |
|-------|---------|
| `checkout.session.completed` | Create subscription record |
| `customer.subscription.created` | Create/update subscription |
| `customer.subscription.updated` | Update subscription status |
| `customer.subscription.deleted` | Mark as canceled |
| `invoice.paid` | Log successful payment |
| `invoice.payment_failed` | Log failure, may trigger alerts |

### Webhook Security

```python
# Signature verification
stripe.Webhook.construct_event(
    payload=request.body,
    sig_header=request.headers["Stripe-Signature"],
    secret=settings.STRIPE_WEBHOOK_SECRET,
)
```

## Seat-Based Pricing

Subscription quantity syncs with organization member count:

```mermaid
flowchart LR
    A[Member added] --> B[Trigger sync]
    B --> C[Count active members]
    C --> D{Quantity changed?}
    D -->|Yes| E[Update Stripe]
    D -->|No| F[Skip]
    E --> G[Prorate billing]
```

**Sync Rules:**
- Quantity updates use proration
- Only syncs for active subscriptions
- Minimum quantity is 1

## Development Without Webhooks

For local development, the `confirm-subscription` endpoint allows syncing subscription status without running `stripe listen`:

```mermaid
sequenceDiagram
    participant Frontend
    participant Backend
    participant Stripe

    Note over Frontend,Stripe: After successful payment
    Frontend->>Backend: POST /confirm-subscription
    Backend->>Stripe: Subscription.retrieve()
    Stripe-->>Backend: Subscription data
    Backend->>Backend: Update local DB
    Backend-->>Frontend: is_active: true
```

> **Production Note:** Always configure webhooks in production for reliability. The confirm endpoint is a development convenience.

## Stripe Configuration

### Environment Variables

```env
# backend/.env
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_ID=price_xxx
```

### Setup Script

```bash
# Create product and price in Stripe
uv run python manage.py setup_stripe
```

This creates:
- Product: "Pro Plan"
- Price: $10/seat/month (or configured amount)

## Frontend Integration

### PaymentForm Component

Uses `@stripe/react-stripe-js` with PaymentElement:

```tsx
import { PaymentElement } from "@stripe/react-stripe-js";

function PaymentForm({ clientSecret, onSuccess }) {
  const stripe = useStripe();
  const elements = useElements();

  const handleSubmit = async () => {
    const { error } = await stripe.confirmPayment({
      elements,
      redirect: "if_required",
    });
    
    if (!error) {
      // Sync subscription status
      await api.confirmSubscription({ subscription_id });
      onSuccess();
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      <button type="submit">Subscribe</button>
    </form>
  );
}
```
