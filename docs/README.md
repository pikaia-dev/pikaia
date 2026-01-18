# System Documentation

Technical documentation for the Tango Django SaaS Starter.

## Contents

### Architecture
- [Overview](./architecture/overview.md) — System architecture and design decisions
- [Data Models](./architecture/data-models.md) — Database schema and relationships

### Features
- [Authentication](./features/authentication.md) — Stytch B2B auth flow
- [Mobile Authentication](./features/mobile-authentication.md) — Mobile provisioning and phone OTP
- [Organizations](./features/organizations.md) — Multi-tenancy and member management
- [Billing](./features/billing.md) — Stripe integration and payment flows

### Guides
- [Local Development](./guides/local-development.md) — Setup and common commands
- [Production Deployment](./guides/production-deployment.md) — AWS deployment with CDK
- [Testing](./guides/testing.md) — Test strategy and running tests

### Operations
- [Observability](./observability.md) — Structured logging, events, and audit trails
- [Webhooks](./webhooks.md) — Customer-facing webhook API

### Planning
- [Roadmap](./ROADMAP.md) — Future enhancements and improvements

## API Reference

API documentation is auto-generated from OpenAPI spec at `/api/v1/docs`.
