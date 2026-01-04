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
| **TangoNetwork** | VPC with public/private subnets, NAT gateway |
| **TangoApp** | Aurora PostgreSQL Serverless v2, ECS Fargate, ALB, Secrets |
| **TangoMedia** | S3 bucket, CloudFront CDN, image transformation Lambda@Edge |
| **TangoEvents** | EventBridge bus, publisher Lambda, SQS DLQ |

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

# With CORS origins for production
npx cdk deploy TangoMedia \
  --context cors_origins='["https://app.example.com"]'
```

### Post-Deployment

1. **Update app secrets**: Add API keys to Secrets Manager
   ```bash
   aws secretsmanager update-secret \
     --secret-id tango/app-secrets \
     --secret-string '{"STYTCH_PROJECT_ID":"...","STYTCH_SECRET":"...","STRIPE_SECRET_KEY":"...","STRIPE_PRICE_ID":"..."}'
   ```

2. **Push Docker image**: Build and push Django app to ECR
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI
   docker build -t $ECR_URI:latest ../backend
   docker push $ECR_URI:latest
   ```

3. **Run migrations**: Execute in ECS task
   ```bash
   aws ecs run-task --cluster TangoCluster --task-definition TangoBackendTask \
     --overrides '{"containerOverrides":[{"name":"django","command":["python","manage.py","migrate"]}]}'
   ```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CloudFront CDN                            │
│                    (Image Transformation)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   S3 Bucket     │    │  Lambda@Edge    │    │   ALB (HTTPS)   │
│  (Media Files)  │◄───│  (Sharp resize) │    │                 │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   ECS Fargate   │
                                              │  (Django App)   │
                                              └────────┬────────┘
                                                       │
                       ┌───────────────────────────────┼───────────────┐
                       │                               │               │
                       ▼                               ▼               ▼
              ┌─────────────────┐            ┌─────────────────┐  ┌─────────────┐
              │ Aurora Postgres │            │   EventBridge   │  │   Secrets   │
              │ Serverless v2   │            │   (tango-bus)   │  │   Manager   │
              └─────────────────┘            └────────┬────────┘  └─────────────┘
                       ▲                              │
                       │                              ▼
              ┌─────────────────┐            ┌─────────────────┐
              │ Publisher Lambda│◄───────────│      SQS DLQ    │
              │ (outbox → EB)   │            │ (failed events) │
              └─────────────────┘            └─────────────────┘
```

## Lambda Functions

### image-transform

Lambda@Edge function for on-the-fly image resizing using Sharp.

**URL Format:**
- `/{width}x{height}/{key}` - Resize to exact dimensions
- `/fit-in/{width}x{height}/{key}` - Fit within dimensions (aspect ratio maintained)
- `/cover/{width}x{height}/{key}` - Cover dimensions (crop to fill)
- `/contain/{width}x{height}/{key}` - Contain within dimensions

**Example:** `https://cdn.example.com/fit-in/200x200/avatars/123/photo.jpg`

### event-publisher

Polls the outbox table and publishes events to EventBridge.

**Trigger:** CloudWatch Events (1-minute interval) + Aurora trigger (future)

**Environment Variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `EVENT_BUS_NAME` - EventBridge bus name
- `BATCH_SIZE` - Events per batch (default: 100)
- `MAX_ATTEMPTS` - Retry attempts before failure (default: 10)

## Cost Optimization

- **NAT Gateway**: Single gateway in dev (use 2+ for production HA)
- **Aurora Serverless v2**: Scales to 0.5 ACU when idle (~$50/month min)
- **ECS Fargate**: Auto-scales 2-10 tasks based on CPU/memory
- **CloudFront**: PRICE_CLASS_100 (US/Canada/Europe only)

## Known Issues

### CDK Python 3.13/3.14 Compatibility

There is a known issue with `jsii` and Python 3.13/3.14 causing:
```
ModuleNotFoundError: No module named 'constructs._jsii'
```

**Workaround:** Use Python 3.12 for CDK operations, or deploy via CI/CD with pinned Python version.

## Pre-deployment Validation

### 1. CDK Synth with Validation Aspects

Built-in validation aspects run during `cdk synth` to check for:
- **Production readiness**: HA configurations, deletion protection
- **Security**: S3 public access, encryption settings

```bash
# Synth with validation (aspects emit warnings/errors)
npx cdk synth --all
```

### 2. CloudFormation Linting

[cfn-lint](https://github.com/aws-cloudformation/cfn-lint) validates synthesized templates:

```bash
# Install dev dependencies (includes cfn-lint)
uv sync --extra dev

# Synth and lint in one command (requires Python 3.12)
npx cdk synth --all && uv run cfn-lint cdk.out/*.template.json
```

> **Note:** cfn-lint currently requires Python 3.12 due to Pydantic v1 compatibility issues with Python 3.13+. Run in CI/CD with pinned Python version.

### 3. Change Set Validation (Native AWS)

For the most thorough pre-deploy check, create change sets without executing:

```bash
# Create change set (runs AWS pre-deployment validation)
npx cdk deploy --no-execute TangoApp

# Review validation in AWS Console or via CLI
aws cloudformation describe-events --change-set-name <ARN>

# Execute if validation passes
npx cdk deploy TangoApp
```

## Testing

```bash
# Validate CDK synth (requires Python 3.12)
npx cdk synth --all

# Run cfn-lint on synthesized templates
uv run cfn-lint cdk.out/*.template.json

# Test image transform Lambda
cd functions/image-transform && npm test

# Test event publisher Lambda
cd functions/event-publisher && uv run pytest tests/
```
