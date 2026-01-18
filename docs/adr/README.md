# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) documenting significant technical decisions made in the Tango SaaS Starter project.

## Index

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [001](./001-stytch-b2b-authentication.md) | Stytch B2B for Authentication | Accepted | Purpose-built B2B auth with organizations, SSO, SCIM |
| [002](./002-transactional-outbox-events.md) | Transactional Outbox for Events | Accepted | Guaranteed event delivery with EventBridge |
| [003](./003-aurora-serverless.md) | Aurora Serverless v2 for Database | Accepted | Auto-scaling PostgreSQL, pay-per-use |
| [004](./004-django-ninja.md) | Django Ninja for REST API | Accepted | FastAPI ergonomics with Django ecosystem |
| [005](./005-resend-email.md) | Resend for Transactional Email | Accepted | React Email native, modern email delivery |
| [006](./006-s3-direct-upload.md) | S3 Direct Upload with Presigned URLs | Accepted | Scalable file uploads without backend bottleneck |
| [007](./007-soft-deletes-audit-trail.md) | Soft Deletes for Audit Trail | Accepted | Compliance-ready data lifecycle management |
| [008](./008-rds-proxy-connection-pooling.md) | RDS Proxy for Connection Pooling | Accepted | Unified connection pool for Lambda + ECS |

## What is an ADR?

An Architecture Decision Record captures a significant architectural decision along with its context and consequences. ADRs help teams:

- **Understand why** decisions were made
- **Onboard new team members** faster
- **Revisit decisions** when context changes
- **Avoid re-debating** settled questions

## ADR Template

```markdown
# ADR [NUMBER]: [TITLE]

**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Date:** [YYYY]

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing and/or doing?

## Rationale
Why is this the best choice among alternatives?

## Consequences
What becomes easier or more difficult because of this decision?

## Implementation Notes
Key technical details for implementers.
```

## Contributing

When making significant architectural decisions:
1. Create a new ADR with the next number
2. Follow the template above
3. Submit with the implementation PR
4. Update this index
