# ADR 005: Resend for Transactional Email

**Status:** Accepted
**Date:** 2026

## Context

We need a transactional email service for:
- User invitations and authentication flows
- Billing notifications (receipts, failed payments)
- System alerts and notifications
- Future: Marketing automation integration

Requirements:
- High deliverability (emails must reach inbox, not spam)
- Modern developer experience (not XML configs)
- React Email compatibility (our template approach)
- Reasonable pricing for startup scale
- Good analytics and debugging tools

Options considered:
1. **AWS SES** - Cheap, but requires warm-up, reputation management, raw SMTP
2. **SendGrid** - Established, but dated API and complex pricing
3. **Postmark** - Great deliverability, but no React Email integration
4. **Resend** - Modern, React Email native, built by email infrastructure experts

## Decision

Use **Resend** as the transactional email provider.

## Rationale

### React Email Integration

Resend is built by the same team as React Email:
```tsx
// emails/invite-member.tsx
import { Button, Text, Html } from '@react-email/components';

export function InviteMemberEmail({ inviteUrl, orgName }) {
  return (
    <Html>
      <Text>You've been invited to join {orgName}</Text>
      <Button href={inviteUrl}>Accept Invitation</Button>
    </Html>
  );
}
```

Benefits:
- Components, not string templates
- TypeScript types for props
- Preview in browser during development
- Version control friendly (it's just React)

### Deliverability Done Right

Resend handles email reputation:
- **Automatic warm-up**: New domains/IPs warmed gradually
- **Dedicated IPs**: Available for high-volume senders
- **DKIM/SPF/DMARC**: Configured automatically
- **Bounce/complaint handling**: Automatic suppression lists

No need to become an email deliverability expert.

### Modern Developer Experience

Simple, intuitive API:
```python
import resend

resend.api_key = settings.RESEND_API_KEY

resend.Emails.send({
    "from": "Tango <noreply@tango.app>",
    "to": member.email,
    "subject": f"You're invited to {org.name}",
    "html": render_email("invite-member", context),
})
```

Features:
- RESTful API with SDKs for all languages
- Webhooks for delivery events
- Real-time logs in dashboard
- Test mode for development

### Analytics and Debugging

Dashboard provides:
- Delivery, open, click, bounce rates
- Per-email delivery timeline
- Error messages for failures
- Search by recipient, subject, status

Debug production issues without digging through logs.

### Pricing Alignment

Resend's pricing fits startup economics:
- **Free tier**: 3,000 emails/month (enough for development)
- **Pro**: $20/month for 50,000 emails
- **No per-email charges** at lower tiers (predictable costs)

Compare to SES's complexity: base rate + data transfer + dedicated IP costs + reputation dashboard.

## Consequences

### Positive
- **React Email native** - First-class support for our template approach
- **High deliverability** - Emails reach inbox without manual reputation work
- **Fast integration** - Simple API, good SDKs, minimal setup
- **Developer tools** - Real-time logs, webhooks, test mode
- **Predictable pricing** - Monthly plans, not metered complexity

### Negative
- **Vendor dependency** - Critical path depends on Resend availability
- **Newer provider** - Less track record than SendGrid/Postmark
- **Cost at scale** - Per-email pricing kicks in at high volume
- **Limited features** - No built-in marketing automation (by design)

### Mitigations
- Email sending is stateless; migration to another provider is straightforward
- Resend team has deep email infrastructure experience (former employees of major providers)
- Can switch to SES for high-volume transactional if economics require
- Marketing automation handled by dedicated tools (Customer.io, etc.)

## Implementation Notes

### Email Template Workflow
```
1. Design in React Email (emails/ directory)
2. Preview with `pnpm email:dev`
3. Build to HTML: `pnpm email:build`
4. Backend renders HTML with context
5. Send via Resend API
```

### Django Integration
```python
# apps/notifications/email.py
import resend
from django.conf import settings

resend.api_key = settings.RESEND_API_KEY

def send_email(
    to: str | list[str],
    subject: str,
    template: str,
    context: dict,
) -> str:
    """Send email via Resend. Returns email ID."""
    html = render_email_template(template, context)

    response = resend.Emails.send({
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": to if isinstance(to, list) else [to],
        "subject": subject,
        "html": html,
    })

    return response["id"]
```

### Webhook Handling
```python
# apps/notifications/webhooks.py
@router.post("/webhooks/resend")
def resend_webhook(request, payload: ResendWebhookPayload):
    match payload.type:
        case "email.delivered":
            log_delivery(payload.data.email_id)
        case "email.bounced":
            handle_bounce(payload.data.email_id, payload.data.bounce_type)
        case "email.complained":
            suppress_recipient(payload.data.to)
```

### Environment Configuration
```bash
# .env
RESEND_API_KEY=re_xxxxx
DEFAULT_FROM_EMAIL="Tango <noreply@mail.tango.app>"

# Use subdomain for transactional email
# mail.tango.app - keeps tango.app reputation clean
```

### Testing
```python
# Resend test mode - emails logged but not sent
# Set RESEND_API_KEY to test key in development

def test_invitation_email():
    email_id = send_invitation_email(
        to="test@example.com",
        org_name="Test Org",
        invite_url="https://app.tango.app/invite/xxx",
    )
    assert email_id is not None
```
