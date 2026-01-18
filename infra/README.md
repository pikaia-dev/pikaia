# Infrastructure (AWS CDK)

AWS CDK stacks for deploying Tango to AWS.

## Prerequisites

- Python 3.12+ (3.12 recommended for CDK compatibility)
- Node.js 20+ (for CDK CLI and Lambda@Edge)
- AWS CLI configured with credentials
- Docker (for Lambda bundling with native dependencies)

## Setup

```bash
cd infra
uv sync

# Install Node.js dependencies for Lambda functions
cd functions/image-transform && npm install && cd ../..
```

## Stacks

| Stack | Description |
|-------|-------------|
| **TangoNetwork** | VPC with public/private subnets, NAT gateway, database security group |
| **TangoApp** | Aurora PostgreSQL Serverless v2, ECS Fargate, ALB, RDS Proxy, Secrets |
| **TangoFrontend** | S3 + CloudFront for React SPA with API routing to ALB |
| **TangoMedia** | S3 bucket, CloudFront CDN, image transformation Lambda@Edge |
| **TangoEvents** | EventBridge bus, publisher Lambda, audit consumer Lambda, SQS DLQs |
| **TangoObservability** | CloudWatch dashboards, alarms, SNS notifications |

## Architecture

### Event-Driven Audit Logging

The `TangoEvents` stack implements an event-driven audit log system:

```
Django Backend
    │
    ▼
OutboxEvent table ──► publish_events command ──► EventBridge
                                                      │
                                     ┌────────────────┴────────────────┐
                                     ▼                                 ▼
                            Audit Consumer Lambda              Other consumers
                            (audit-consumer/)
                                     │
                                     ▼
                              AuditLog table
```

**Components:**
- **Event Publisher Lambda**: Polls outbox table and publishes to EventBridge
- **Audit Consumer Lambda**: Subscribes to audit-worthy events, creates AuditLog entries
- **Dead Letter Queues**: Capture failed events for investigation (14-day retention)
- **RDS Proxy**: Connection pooling for Lambda → Aurora connections

### Audit Event Types

The audit consumer processes these event types (defined in `generate_audit_schema.py`):
- `member.invited`, `member.bulk_invited`, `member.joined`, `member.removed`, `member.role_changed`
- `organization.created`, `organization.updated`, `organization.billing_updated`
- `user.profile_updated`, `user.phone_changed`

## Deployment

### First-time Setup

```bash
# Bootstrap CDK (once per account/region)
npx cdk bootstrap aws://ACCOUNT_ID/REGION

# Deploy foundation stacks
npx cdk deploy TangoNetwork TangoApp
```

### Full Deployment

```bash
# Deploy all stacks
npx cdk deploy --all

# With custom domain and certificate
npx cdk deploy TangoApp \
  --context domain_name=api.example.com \
  --context certificate_arn=arn:aws:acm:us-east-1:123456789:certificate/xxx
```

### Updating Audit Schema

When modifying the `AuditLog` model:

```bash
# 1. Regenerate schema (from backend/)
uv run python manage.py generate_audit_schema

# 2. Commit the generated file
git add infra/functions/audit-consumer/generated_schema.py

# 3. Deploy updated Lambda
npx cdk deploy TangoEvents
```

CI validates the schema is up-to-date via `--check` flag.

## Lambda Functions

| Function | Directory | Purpose |
|----------|-----------|---------|
| **event-publisher** | `functions/event-publisher/` | Polls outbox, publishes to EventBridge |
| **audit-consumer** | `functions/audit-consumer/` | Creates audit logs from events |
| **image-transform** | `functions/image-transform/` | Lambda@Edge for image resizing |

## Outputs

Key CloudFormation outputs after deployment:

- `TangoApiDns` - ALB DNS name for API
- `TangoDatabaseEndpoint` - Aurora cluster endpoint
- `TangoRdsProxyEndpoint` - RDS Proxy endpoint (for Lambda)
- `TangoEventBusArn` - EventBridge bus ARN
- `TangoAuditDLQUrl` - Audit consumer DLQ URL
