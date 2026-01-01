# Billing API Reference

Base URL: `/api/v1/billing`

All endpoints require authentication unless noted. Admin-only endpoints require the `admin` role.

## Endpoints

### Get Subscription

```
GET /subscription
```

Get the current organization's subscription status.

**Response (subscribed):**
```json
{
  "status": "active",
  "quantity": 5,
  "current_period_end": "2024-02-01T00:00:00+00:00",
  "cancel_at_period_end": false,
  "stripe_customer_id": "cus_xxx"
}
```

**Response (free tier):**
```json
{
  "status": "none",
  "quantity": 3,
  "current_period_end": null,
  "cancel_at_period_end": false,
  "stripe_customer_id": ""
}
```

**Status Values:**
| Status | Description |
|--------|-------------|
| `none` | No subscription (free tier) |
| `active` | Paid and usable |
| `trialing` | In trial period |
| `past_due` | Payment failed, grace period |
| `canceled` | Subscription ended |
| `incomplete` | Initial payment pending |
| `incomplete_expired` | Initial payment failed |

---

### Create Checkout Session (Admin)

```
POST /checkout
```

Create a Stripe Checkout session for redirect-based payment.

**Requires:** Admin role

**Request:**
```json
{
  "success_url": "https://app.example.com/billing?success=true",
  "cancel_url": "https://app.example.com/billing",
  "quantity": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success_url` | string | Yes | Redirect URL after successful payment |
| `cancel_url` | string | Yes | Redirect URL if user cancels |
| `quantity` | integer | No | Number of seats (defaults to member count) |

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_xxx"
}
```

**Errors:**
- `400` — Already subscribed
- `403` — Admin access required

---

### Create Subscription Intent (Admin)

```
POST /subscription-intent
```

Create a subscription for in-app payment with Stripe Elements.

**Requires:** Admin role

**Request:**
```json
{
  "quantity": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `quantity` | integer | No | Number of seats (defaults to member count) |

**Response:**
```json
{
  "client_secret": "pi_xxx_secret_xxx",
  "subscription_id": "sub_xxx"
}
```

**Errors:**
- `400` — Already subscribed
- `403` — Admin access required

**Usage:**
```typescript
// Frontend: Use with PaymentElement
const { clientSecret, subscriptionId } = await api.createSubscriptionIntent();

const { error } = await stripe.confirmPayment({
  elements,
  clientSecret,
  redirect: "if_required",
});

if (!error) {
  await api.confirmSubscription({ subscription_id: subscriptionId });
}
```

---

### Confirm Subscription (Admin)

```
POST /confirm-subscription
```

Sync subscription status from Stripe after payment. Useful for development without webhooks.

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

**Errors:**
- `403` — Admin access required
- `500` — Stripe API error

---

### Create Portal Session (Admin)

```
POST /portal
```

Create a Stripe Customer Portal session for self-service billing management.

**Requires:** Admin role, existing customer

**Request:**
```json
{
  "return_url": "https://app.example.com/billing"
}
```

**Response:**
```json
{
  "portal_url": "https://billing.stripe.com/p/session/xxx"
}
```

**Errors:**
- `400` — No Stripe customer exists
- `403` — Admin access required

---

## Webhook Endpoint

```
POST /webhooks/stripe/
```

Receives Stripe webhook events. Defined outside Django Ninja at `/webhooks/stripe/` for raw request handling.

**Authentication:** Stripe signature verification

**Handled Events:**
- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
| Code | Description |
|------|-------------|
| `400` | Bad request (invalid input, already subscribed) |
| `401` | Unauthorized (missing or invalid JWT) |
| `403` | Forbidden (admin access required) |
| `500` | Server error (Stripe API failure) |
