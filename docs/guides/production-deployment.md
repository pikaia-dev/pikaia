# AWS Production Deployment Guide

This guide covers deploying the application to AWS using CDK.

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK installed (`npm install -g aws-cdk`)
- Docker installed and running
- Python 3.12+ with uv

## Architecture Overview

The deployment creates:
- **VPC** with public/private subnets
- **Aurora PostgreSQL** serverless v2 database
- **ECS Fargate** running the Django application
- **Application Load Balancer** for traffic distribution
- **ECR** for Docker image storage
- **Secrets Manager** for sensitive configuration
- **EventBridge** for event-driven architecture
- **S3 + CloudFront** for media storage with image transformation
- **S3 + CloudFront** for frontend SPA hosting
- **CloudWatch** dashboards and alarms for observability

## Step 1: Configure AWS Profile

```bash
# Verify your AWS profile is configured
aws configure list --profile your-profile-name
```

## Step 2: Bootstrap CDK (First Time Only)

```bash
cd infra
AWS_PROFILE=your-profile npx cdk bootstrap
```

## Step 3: Set Up Production Secrets

### 3.1 Create the secrets file

```bash
# From project root
cp .env.production.example .env.production
```

### 3.2 Fill in your secrets

Edit `.env.production` with real values:

| Variable | Source |
|----------|--------|
| `DJANGO_SECRET_KEY` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `STYTCH_PROJECT_ID` | [Stytch Dashboard](https://stytch.com/dashboard) → API Keys |
| `STYTCH_SECRET` | [Stytch Dashboard](https://stytch.com/dashboard) → API Keys |
| `STRIPE_SECRET_KEY` | [Stripe Dashboard](https://dashboard.stripe.com/apikeys) |
| `STRIPE_PRICE_ID` | [Stripe Dashboard](https://dashboard.stripe.com/products) → Your product → Price ID |
| `STRIPE_WEBHOOK_SECRET` | See Step 5 below |
| `RESEND_API_KEY` | [Resend Dashboard](https://resend.com/api-keys) |
| `WEBAUTHN_RP_ID` | Your domain (e.g., `app.example.com`) |
| `WEBAUTHN_RP_NAME` | Display name for passkey prompts |
| `WEBAUTHN_ORIGIN` | Full HTTPS URL (e.g., `https://app.example.com`) |
| `STYTCH_TRUSTED_AUTH_PROFILE_ID` | [Stytch Dashboard](https://stytch.com/dashboard/trusted-auth-tokens) → Create profile |
| `STYTCH_TRUSTED_AUTH_AUDIENCE` | Must match Stytch profile (default: `stytch`) |
| `STYTCH_TRUSTED_AUTH_ISSUER` | Must match Stytch profile (default: `passkey-auth`) |
| `PASSKEY_JWT_PRIVATE_KEY` | RSA private key PEM (newlines escaped as `\n`) |
| `CORS_ALLOWED_ORIGINS` | Frontend URL(s), comma-separated (e.g., `https://app.example.com`) |

### 3.3 Push secrets to AWS

```bash
./scripts/bootstrap-secrets.sh your-profile-name
```

## Step 4: Build and Push Docker Image

```bash
cd backend

# Login to ECR
AWS_PROFILE=your-profile aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build for linux/amd64 (required for ECS Fargate)
docker build --platform linux/amd64 -t pikaia-backend:latest .

# Tag and push
docker tag pikaia-backend:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pikaia-backend:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pikaia-backend:latest
```

## Step 5: Deploy Infrastructure

```bash
cd infra
AWS_PROFILE=your-profile npx cdk deploy --all --require-approval never
```

This will output your ALB URL, e.g.:
```
PikaiaApp.LoadBalancerDNS = Pikaia-XXXXX.us-east-1.elb.amazonaws.com
```

## Step 6: Configure Stripe Webhook

1. Go to [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click **"Add endpoint"**
3. Enter your endpoint URL:
   ```
   https://your-domain.com/api/v1/billing/webhooks/stripe/
   ```
   Or for testing (HTTP):
   ```
   http://YOUR_ALB_URL/api/v1/billing/webhooks/stripe/
   ```
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
5. Click **"Add endpoint"**
6. Click **"Reveal"** under Signing secret → copy `whsec_...`
7. Add to `.env.production` and re-run `./scripts/bootstrap-secrets.sh`

## Step 7: Run Database Migrations

```bash
# Connect via ECS Exec (requires ECS Exec enabled)
AWS_PROFILE=your-profile aws ecs execute-command \
  --cluster YOUR_CLUSTER_NAME \
  --task YOUR_TASK_ID \
  --container django \
  --interactive \
  --command "/bin/bash"

# Inside container:
python manage.py migrate
```

## Step 8: Force New Deployment (After Config Changes)

```bash
AWS_PROFILE=your-profile aws ecs update-service \
  --cluster YOUR_CLUSTER_NAME \
  --service YOUR_SERVICE_NAME \
  --force-new-deployment
```

## Verification

Test the health endpoint:
```bash
curl http://YOUR_ALB_URL/api/v1/health
# Should return: {"status": "ok"}
```

## Troubleshooting

### Tasks Failing to Start
- Check CloudWatch logs for the ECS task
- Verify secrets are populated in AWS Secrets Manager
- Ensure Docker image is built for `linux/amd64`

### Health Checks Failing
- Health check path: `/api/v1/health` (no trailing slash)
- Verify security groups allow traffic on port 8000
- Check Django `ALLOWED_HOSTS` includes the ALB hostname

### Database Connection Issues
- Verify the database security group allows inbound from ECS security group
- Check secrets contain correct database credentials

## Continuous Deployment (Push-to-Deploy)

The repository includes GitHub Actions workflows for automatic deployment:

### Backend (`deploy-ecs.yml`)
- **Trigger**: Push to `main` with changes in `backend/`, `emails/`, or `infra/`
- **Concurrency**: `cancel-in-progress: true` - rapid pushes cancel previous deployments
- **Steps**: Build Docker image → Push to ECR → Update task definition → Deploy ECS service → Run migrations

### Frontend (`deploy-frontend.yml`)
- **Trigger**: Push to `main` with changes in `frontend/`
- **Concurrency**: `cancel-in-progress: true` - rapid pushes cancel previous deployments
- **Steps**: Build Vite app → Sync to S3 → Invalidate CloudFront cache

### Required GitHub Secrets/Vars

| Type | Name | Description |
|------|------|-------------|
| Secret | `AWS_OIDC_ROLE_ARN` | IAM role ARN for GitHub OIDC |
| Var | `AWS_REGION` | AWS region (e.g., `us-east-1`) |
| Var | `ECR_REPOSITORY` | Full ECR URI |
| Var | `ECS_CLUSTER` | ECS cluster name |
| Var | `ECS_SERVICE` | ECS service name |
| Var | `ECS_TASK_DEFINITION` | Task definition family name |
| Var | `FRONTEND_BUCKET` | S3 bucket for frontend |
| Var | `CLOUDFRONT_DISTRIBUTION_ID` | Frontend CloudFront ID |
| Var | `VITE_API_URL` | Backend API URL for frontend build |
| Secret | `VITE_STYTCH_PUBLIC_TOKEN` | Stytch public token (required) |
| Var | `VITE_STRIPE_PUBLISHABLE_KEY` | Stripe publishable key (optional) |
| Var | `VITE_GOOGLE_PLACES_API_KEY` | Google Places API key (optional) |


## Observability

The `PikaiaObservability` stack deploys CloudWatch dashboards and alarms automatically. To enable email notifications for alarms:

```bash
AWS_PROFILE=your-profile npx cdk deploy PikaiaObservability --context alarm_email=ops@example.com
```

See [Observability Guide](../observability.md) for:
- Structured logging configuration and field conventions
- CloudWatch Logs Insights queries
- Dashboard and alarm customization
- Correlation between logs, events, and audit trails

## Next Steps

- [ ] Configure custom domain with Route 53
- [ ] Subscribe to alarm SNS topic (PagerDuty, Slack, etc.)
- [ ] Enable ECS Exec for container access
