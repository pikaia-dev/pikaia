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
echo "Next steps:"
echo "  1. Run ./scripts/bootstrap-secrets.sh to populate API keys"
echo "  2. Build and push Docker image to ECR"
echo "  3. Run cdk deploy to deploy the application stack"
