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

## Step 2: Set Up Infra Dependencies

```bash
cd infra
uv sync

# Install Node.js dependencies for Lambda functions
cd functions/image-transform && npm install && cd ../..
```

## Step 3: Bootstrap CDK (First Time Only)

```bash
AWS_PROFILE=your-profile npx cdk bootstrap
```

## Step 4: Set Up Production Secrets

### 4.1 Create the secrets file

```bash
# From project root
cp .env.production.example .env.production
```

### 4.2 Fill in your secrets

Edit `.env.production` with real values:

| Variable | Source |
|----------|--------|
| `DJANGO_SECRET_KEY` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `STYTCH_PROJECT_ID` | [Stytch Dashboard](https://stytch.com/dashboard) → API Keys |
| `STYTCH_SECRET` | [Stytch Dashboard](https://stytch.com/dashboard) → API Keys |
| `STRIPE_SECRET_KEY` | [Stripe Dashboard](https://dashboard.stripe.com/apikeys) |
| `STRIPE_PRICE_ID` | [Stripe Dashboard](https://dashboard.stripe.com/products) → Your product → Price ID |
| `STRIPE_WEBHOOK_SECRET` | See Step 8 below |
| `RESEND_API_KEY` | [Resend Dashboard](https://resend.com/api-keys) |
| `WEBAUTHN_RP_ID` | Your domain (e.g., `app.example.com`) |
| `WEBAUTHN_RP_NAME` | Display name for passkey prompts |
| `WEBAUTHN_ORIGIN` | Full HTTPS URL (e.g., `https://app.example.com`) |
| `STYTCH_TRUSTED_AUTH_PROFILE_ID` | [Stytch Dashboard](https://stytch.com/dashboard/trusted-auth-tokens) → Create profile |
| `STYTCH_TRUSTED_AUTH_AUDIENCE` | Must match Stytch profile (default: `stytch`) |
| `STYTCH_TRUSTED_AUTH_ISSUER` | Must match Stytch profile (default: `passkey-auth`) |
| `PASSKEY_JWT_PRIVATE_KEY` | RSA private key PEM (newlines escaped as `\n`) |
| `CORS_ALLOWED_ORIGINS` | Frontend URL(s), comma-separated (e.g., `https://app.example.com`) |

### 4.3 Create AWS resources (ECR + Secrets Manager)

```bash
./scripts/bootstrap-infra.sh your-profile-name
```

This creates:
- ECR repository (`pikaia-backend`) for Docker images
- Secrets Manager secret (`pikaia/app-secrets`) as an empty placeholder

### 4.4 Push secrets to AWS

```bash
./scripts/bootstrap-secrets.sh your-profile-name
```

## Step 5: Build and Push Docker Image

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

## Step 6: Create SSL Certificate (ACM)

Before deploying with HTTPS, create an SSL certificate in AWS Certificate Manager:

```bash
# Request certificate for your API domain
aws acm request-certificate \
  --domain-name api.yourdomain.com \
  --validation-method DNS \
  --profile your-profile \
  --region us-east-1

# Copy the certificate ARN from the output
```

Then add DNS validation records:
1. Go to [ACM Console](https://console.aws.amazon.com/acm/home?region=us-east-1#/certificates/list)
2. Click on your certificate → Copy the CNAME name and value
3. Add as CNAME record in your DNS provider (DNS only, not proxied)
4. Wait 5-10 minutes for validation

## Step 7: Deploy Infrastructure

```bash
cd infra

# First deployment (HTTP only for testing)
AWS_PROFILE=your-profile npx cdk deploy --all

# Production deployment (with HTTPS)
AWS_PROFILE=your-profile npx cdk deploy PikaiaApp \
  --context certificate_arn=arn:aws:acm:us-east-1:YOUR_ACCOUNT:certificate/CERT_ID \
  --context domain_name=api.yourdomain.com
```

This will output your ALB URL, e.g.:
```
PikaiaApp.LoadBalancerDNS = Pikaia-XXXXX.us-east-1.elb.amazonaws.com
```

## Step 8: Configure Stripe Webhook

1. Go to [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click **"Add endpoint"**
3. Enter your endpoint URL:
   ```
   https://your-domain.com/webhooks/stripe/
   ```
   Or for testing (HTTP):
   ```
   http://YOUR_ALB_URL/webhooks/stripe/
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

## Step 9: Run Database Migrations

### Option A: One-off task (recommended)

Run migrations as a standalone task:

```bash
# Get required IDs
CLUSTER=$(aws ecs list-clusters --query 'clusterArns[0]' --output text --profile your-profile)
TASK_DEF=$(aws ecs list-task-definitions --family-prefix PikaiaApp --query 'taskDefinitionArns[-1]' --output text --profile your-profile)
SUBNET=$(aws ec2 describe-subnets --filters 'Name=tag:aws-cdk:subnet-type,Values=Public' --query 'Subnets[0].SubnetId' --output text --profile your-profile)
SG=$(aws ec2 describe-security-groups --filters 'Name=group-name,Values=*EcsServiceSG*' --query 'SecurityGroups[0].GroupId' --output text --profile your-profile)

# Run migrations
aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition $TASK_DEF \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"django","command":["python","manage.py","migrate"]}]}' \
  --profile your-profile

# Check logs after ~60 seconds
aws logs tail PikaiaApp-PikaiaBackendTask* --since 5m --profile your-profile
```

### Option B: ECS Exec (interactive)

```bash
# Enable ECS Exec on the service (one-time)
aws ecs update-service --cluster YOUR_CLUSTER --service YOUR_SERVICE --enable-execute-command --profile your-profile

# Wait for new tasks, then connect
aws ecs execute-command \
  --cluster YOUR_CLUSTER \
  --task YOUR_TASK_ID \
  --container django \
  --interactive \
  --command "/bin/bash" \
  --profile your-profile

# Inside container:
python manage.py migrate
```

> **Note**: ECS Exec requires the Session Manager plugin and can have connectivity issues. Option A is more reliable for one-off commands.

## Step 10: Force New Deployment (After Config Changes)

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
- Verify secrets are populated in AWS Secrets Manager — each key referenced by the ECS task definition must exist in the secret JSON (including `STYTCH_WEBHOOK_SECRET` and `MOBILE_PROVISION_API_KEY`)
- Ensure Docker image is built for `linux/amd64` (Mac builds default to ARM64)

### Health Checks Failing (DisallowedHost)

ALB health checks use the container's **private IP** as the `Host` header (e.g., `10.0.3.82:8000`). Django's `SecurityMiddleware` rejects these via `ALLOWED_HOSTS` before the request reaches the health endpoint.

**Fix**: `HealthCheckMiddleware` in `apps.core.middleware` intercepts requests to `/api/v1/health` *before* `SecurityMiddleware` and returns `200` directly. It must be first in the `MIDDLEWARE` list.

If you see `DisallowedHost: Invalid HTTP_HOST header` in CloudWatch logs for health check requests, verify the middleware ordering in `config/settings/base.py`.

### Database Connection Issues
- Verify the database security group allows inbound from ECS security group
- Check secrets contain correct database credentials

### CDK Bootstrap Broken (CDKToolkit Stack)

If `CDKToolkit` is stuck in `ROLLBACK_COMPLETE` or `REVIEW_IN_PROGRESS`:

```bash
# 1. Delete the CDKToolkit stack
aws cloudformation delete-stack --stack-name CDKToolkit --profile your-profile

# 2. Empty and delete the orphaned S3 assets bucket (has versioning enabled)
BUCKET=cdk-hnb659fds-assets-ACCOUNT_ID-REGION
aws s3api list-object-versions --bucket $BUCKET --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json | \
  aws s3api delete-objects --bucket $BUCKET --delete file:///dev/stdin
aws s3api list-object-versions --bucket $BUCKET --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json | \
  aws s3api delete-objects --bucket $BUCKET --delete file:///dev/stdin
aws s3 rb s3://$BUCKET --profile your-profile

# 3. Re-bootstrap
AWS_PROFILE=your-profile npx cdk bootstrap aws://ACCOUNT_ID/REGION
```

### Aurora Deletion Protection Blocking Rollback

CDK sets `deletion_protection=True` on Aurora clusters. If a deployment fails and CloudFormation rolls back, it can't delete the database, causing `ROLLBACK_FAILED`.

```bash
# Disable deletion protection to allow rollback
aws rds modify-db-cluster \
  --db-cluster-identifier CLUSTER_ID \
  --no-deletion-protection \
  --profile your-profile

# Then continue the rollback
aws cloudformation continue-update-rollback --stack-name PikaiaApp --profile your-profile
```

### SQS Queue Name Cooldown

After deleting SQS queues, AWS enforces a **60-second cooldown** before queues with the same name can be recreated. If `PikaiaEvents` fails with "queue already exists" errors, wait 60 seconds and retry.

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

### Setting Up AWS OIDC for GitHub Actions

GitHub Actions uses OIDC to authenticate with AWS (no static credentials needed).

**1. Create the OIDC provider (one-time per AWS account):**
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 1c58a3a8518e8759bf075b76b750d4f2df264fcd \
  --profile your-profile
```

**2. Create the IAM role with trust policy:**
```bash
# Create trust-policy.json (replace YOUR_ACCOUNT_ID and YOUR_ORG/YOUR_REPO)
cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": { "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/YOUR_REPO:*" }
    }
  }]
}
EOF

aws iam create-role \
  --role-name GitHubActionsDeployRole \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  --profile your-profile
```

**3. Attach deployment permissions:**
The role needs: S3 (frontend), CloudFront (invalidation), ECR (images), ECS (deployment).

```bash
# Attach managed policies or create custom policy
aws iam attach-role-policy \
  --role-name GitHubActionsDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess \
  --profile your-profile
# Add more policies as needed for ECR, ECS, CloudFront
```

**4. Copy the role ARN for GitHub:**
```
arn:aws:iam::YOUR_ACCOUNT_ID:role/GitHubActionsDeployRole
```


## Observability

The `PikaiaObservability` stack deploys CloudWatch dashboards and alarms automatically. To enable email notifications for alarms:

```bash
AWS_PROFILE=your-profile npx cdk deploy PikaiaObservability --context alarm_email=ops@example.com
```

See [Observability Guide](../operations/observability.md) for:
- Structured logging configuration and field conventions
- CloudWatch Logs Insights queries
- Dashboard and alarm customization
- Correlation between logs, events, and audit trails

## Shared Infrastructure Mode

Pikaia supports sharing infrastructure (VPC, ALB, Aurora) across multiple deployments to reduce costs. There are two CDK context flags that control this:

- **`export_shared_infra_prefix`** — Deploy as a provider: creates all resources and exports them as SSM parameters for other deployments to consume.
- **`shared_infra_prefix`** — Deploy as a consumer: skips VPC/ALB/Aurora creation and reads them from SSM parameters.

### Deploy as Provider (Export)

```bash
cd infra && npx cdk deploy --all \
  --context export_shared_infra_prefix=/shared-infra/prod \
  --context certificate_arn=arn:aws:acm:... \
  --context domain_name=api.yourdomain.com
```

### Deploy as Consumer (Shared)

```bash
# First, create a database in the shared Aurora cluster
./scripts/create-project-database.sh myproject <cluster-endpoint>

# Then deploy
cd infra && npx cdk deploy --all \
  --context shared_infra_prefix=/shared-infra/prod \
  --context domain_name=api.myproject.com \
  --context alb_rule_priority=200
```

See [Shared Infrastructure Architecture](../architecture/shared-infrastructure.md) for full details on setup, configuration, and troubleshooting.

## Next Steps

- [ ] Configure custom domain with Route 53
- [ ] Subscribe to alarm SNS topic (PagerDuty, Slack, etc.)
- [ ] Enable ECS Exec for container access
