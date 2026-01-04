#!/usr/bin/env bash
# =============================================================================
# Bootstrap Secrets for AWS Deployment
# =============================================================================
# Usage: ./scripts/bootstrap-secrets.sh [profile]
#
# This script populates AWS Secrets Manager with production secrets.
# Run this ONCE per environment during initial setup.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - .env.production file with required secrets
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env.production"

# AWS profile (default or from argument)
AWS_PROFILE="${1:-tango-b2b-demo}"
export AWS_PROFILE

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

# Check env file exists
if [[ ! -f "$ENV_FILE" ]]; then
    echo_error "Environment file not found: $ENV_FILE"
    echo_info "Create it from the example:"
    echo "  cp .env.production.example .env.production"
    echo "  # Then edit with your real values"
    exit 1
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

# Required variables
REQUIRED_VARS=(
    "DJANGO_SECRET_KEY"
    "STYTCH_PROJECT_ID"
    "STYTCH_SECRET"
    "STRIPE_SECRET_KEY"
    "STRIPE_PRICE_ID"
)

# Validate all required vars are set
missing=()
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        missing+=("$var")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    echo_error "Missing required variables in $ENV_FILE:"
    for var in "${missing[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

echo_info "Using AWS profile: $AWS_PROFILE"
echo_info "Reading secrets from: $ENV_FILE"

# Confirm before proceeding
echo ""
echo_warn "This will update AWS Secrets Manager with values from .env.production"
read -p "Continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo_info "Aborted."
    exit 0
fi

# Build JSON from env vars
SECRET_JSON=$(cat <<EOF
{
  "DJANGO_SECRET_KEY": "$DJANGO_SECRET_KEY",
  "STYTCH_PROJECT_ID": "$STYTCH_PROJECT_ID",
  "STYTCH_SECRET": "$STYTCH_SECRET",
  "STRIPE_SECRET_KEY": "$STRIPE_SECRET_KEY",
  "STRIPE_PRICE_ID": "$STRIPE_PRICE_ID"
}
EOF
)

# Update secrets
SECRET_NAME="tango/app-secrets"
echo_info "Updating secret: $SECRET_NAME"

VERSION_ID=$(aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string "$SECRET_JSON" \
    --query 'VersionId' \
    --output text)

echo_info "Secret updated! Version: $VERSION_ID"
echo ""
echo_info "Next: Force ECS deployment to pick up new secrets:"
echo "  aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment"
