#!/usr/bin/env bash
# =============================================================================
# Bootstrap Infrastructure Prerequisites for AWS Deployment
# =============================================================================
# Usage: ./scripts/bootstrap-infra.sh [profile]
#
# This script creates infrastructure prerequisites that must exist BEFORE
# running CDK deploy. These resources are created outside of CDK because
# they need to persist across stack destroy/recreate cycles.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#
# Created resources:
#   - ECR repository: pikaia-backend (for Docker images)
#   - Secrets Manager secret: pikaia/app-secrets (for API keys)
# =============================================================================

set -euo pipefail

# AWS profile (default or from argument)
AWS_PROFILE="${1:-pikaia}"
export AWS_PROFILE

# Resource names (can be overridden via environment variables)
RESOURCE_PREFIX="${RESOURCE_PREFIX:-pikaia}"
ECR_REPO_NAME="${ECR_REPO_NAME:-${RESOURCE_PREFIX}-backend}"
SECRETS_NAME="${SECRETS_NAME:-${RESOURCE_PREFIX}/app-secrets}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo_error "AWS CLI is required but not installed."
    exit 1
fi

echo_info "Using AWS profile: $AWS_PROFILE"
echo ""

# =============================================================================
# ECR Repository
# =============================================================================
echo_info "Checking ECR repository: $ECR_REPO_NAME"

if aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" &> /dev/null; then
    echo_info "ECR repository already exists: $ECR_REPO_NAME"
else
    echo_info "Creating ECR repository: $ECR_REPO_NAME"
    aws ecr create-repository \
        --repository-name "$ECR_REPO_NAME" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256 \
        --query 'repository.repositoryUri' \
        --output text
    echo_info "ECR repository created successfully"
fi

# Apply lifecycle policy to expire untagged images after 30 days
echo_info "Applying ECR lifecycle policy to: $ECR_REPO_NAME"
aws ecr put-lifecycle-policy \
    --repository-name "$ECR_REPO_NAME" \
    --lifecycle-policy-text '{
        "rules": [
            {
                "rulePriority": 1,
                "description": "Expire untagged images after 30 days",
                "selection": {
                    "tagStatus": "untagged",
                    "countType": "sinceImagePushed",
                    "countUnit": "days",
                    "countNumber": 30
                },
                "action": {
                    "type": "expire"
                }
            }
        ]
    }' > /dev/null
echo_info "ECR lifecycle policy applied successfully"

# =============================================================================
# Secrets Manager Secret (placeholder - real values via bootstrap-secrets.sh)
# =============================================================================
echo_info "Checking Secrets Manager secret: $SECRETS_NAME"

if aws secretsmanager describe-secret --secret-id "$SECRETS_NAME" &> /dev/null; then
    echo_info "Secrets Manager secret already exists: $SECRETS_NAME"
else
    echo_info "Creating Secrets Manager secret placeholder: $SECRETS_NAME"
    aws secretsmanager create-secret \
        --name "$SECRETS_NAME" \
        --description "Application secrets (API keys, etc.)" \
        --secret-string '{"placeholder": "run bootstrap-secrets.sh to populate"}' \
        --query 'ARN' \
        --output text
    echo_info "Secrets Manager secret created successfully"
    echo_warn "Run ./scripts/bootstrap-secrets.sh to populate with real values"
fi

echo ""
echo_info "Infrastructure prerequisites complete!"
echo ""

# =============================================================================
# Shared Infrastructure Configuration (optional)
# =============================================================================
echo "Would you like to configure shared infrastructure?"
echo ""
echo "  1) Export (provider) - This deployment exports its resources via SSM"
echo "     so other projects can consume them in shared mode."
echo ""
echo "  2) Consume (shared) - This deployment uses infrastructure from an"
echo "     existing provider deployment via SSM parameters."
echo ""
echo "  3) Skip - Standalone only, no shared infrastructure."
echo ""
read -rp "Choose [1/2/3] (default: 3): " shared_choice
shared_choice="${shared_choice:-3}"

case "$shared_choice" in
    1)
        read -rp "SSM prefix for export (default: /shared-infra/prod): " export_prefix
        export_prefix="${export_prefix:-/shared-infra/prod}"
        echo ""
        echo_info "To deploy as a shared infrastructure provider, run:"
        echo ""
        echo "  cd infra && npx cdk deploy --all \\"
        echo "    --context export_shared_infra_prefix=${export_prefix} \\"
        echo "    --context certificate_arn=arn:aws:acm:REGION:ACCOUNT:certificate/ID \\"
        echo "    --context domain_name=api.yourdomain.com"
        echo ""
        echo_info "HTTPS (certificate_arn) is required for export mode."
        echo_info "The provider's database is created automatically by CDK."
        ;;
    2)
        read -rp "SSM prefix to consume from (default: /shared-infra/prod): " shared_prefix
        shared_prefix="${shared_prefix:-/shared-infra/prod}"
        read -rp "API domain name (e.g., api.myproject.com): " api_domain
        read -rp "ALB listener rule priority (100-999, must be unique): " rule_priority
        echo ""
        echo_warn "Before deploying, create your project database in the shared Aurora cluster:"
        echo "  ./scripts/create-project-database.sh ${RESOURCE_PREFIX} <cluster-endpoint>"
        echo ""
        echo_info "Then deploy as a shared infrastructure consumer:"
        echo ""
        echo "  cd infra && npx cdk deploy --all \\"
        echo "    --context shared_infra_prefix=${shared_prefix} \\"
        echo "    --context domain_name=${api_domain} \\"
        echo "    --context alb_rule_priority=${rule_priority}"
        echo ""
        ;;
    *)
        echo ""
        echo "Next steps:"
        echo "  1. Run ./scripts/bootstrap-secrets.sh to populate API keys"
        echo "  2. Build and push Docker image to ECR"
        echo "  3. Run cdk deploy to deploy the application stack"
        ;;
esac
