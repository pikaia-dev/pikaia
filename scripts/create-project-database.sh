#!/usr/bin/env bash
# =============================================================================
# Create Project Database in Shared Aurora Cluster
# =============================================================================
# Usage: ./scripts/create-project-database.sh <project-prefix> <cluster-endpoint> [profile]
#
# This script is only needed when adding a CONSUMER project to a shared Aurora
# cluster. The provider project's database is created automatically by CDK
# (via default_database_name in the Aurora cluster construct).
#
# Each additional consumer needs its own database, user, and credentials
# within the same cluster.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - psql (PostgreSQL client) installed
#   - Network access to the Aurora cluster (e.g., via VPN or bastion host)
#   - Master database credentials (from the provider's Secrets Manager)
#
# Created resources:
#   - PostgreSQL database: <project-prefix>
#   - PostgreSQL user: <project-prefix>_user
#   - Secrets Manager secret: <project-prefix>/database-credentials
# =============================================================================

set -euo pipefail

# Arguments
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <project-prefix> <cluster-endpoint> [aws-profile]"
    echo ""
    echo "Arguments:"
    echo "  project-prefix    Prefix for database, user, and secret names"
    echo "  cluster-endpoint  Aurora cluster endpoint hostname"
    echo "  aws-profile       AWS CLI profile (default: pikaia)"
    echo ""
    echo "Example:"
    echo "  $0 myproject prod-cluster.cluster-abc123.us-east-1.rds.amazonaws.com"
    exit 1
fi

PROJECT_PREFIX="$1"
CLUSTER_ENDPOINT="$2"
AWS_PROFILE="${3:-pikaia}"
export AWS_PROFILE

# Validate project prefix (must be a safe PostgreSQL identifier)
if [[ ! "$PROJECT_PREFIX" =~ ^[a-z][a-z0-9_]*$ ]]; then
    echo "Error: project-prefix must start with a lowercase letter and contain only"
    echo "       lowercase letters, digits, and underscores (e.g., 'myproject', 'app_v2')."
    exit 1
fi

DB_NAME="${PROJECT_PREFIX}"
DB_USER="${PROJECT_PREFIX}_user"
DB_PASSWORD=$(openssl rand -base64 32)
SECRET_NAME="${PROJECT_PREFIX}/database-credentials"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
if ! command -v psql &> /dev/null; then
    echo_error "psql is required but not installed."
    echo "  Install: brew install libpq && brew link --force libpq"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo_error "AWS CLI is required but not installed."
    exit 1
fi

echo_info "Creating database for project: $PROJECT_PREFIX"
echo_info "Cluster endpoint: $CLUSTER_ENDPOINT"
echo_info "AWS profile: $AWS_PROFILE"
echo ""

# Check if secret already exists
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" &> /dev/null; then
    echo_error "Secret '$SECRET_NAME' already exists. Database may already be set up."
    echo "  To recreate, first delete the existing secret:"
    echo "  aws secretsmanager delete-secret --secret-id $SECRET_NAME --force-delete-without-recovery"
    exit 1
fi

# Create database and user
echo_info "Connecting to Aurora cluster as master user..."
echo_warn "You will be prompted for the master password."
echo_warn "(Find it in the provider's Secrets Manager under the database secret)"
echo ""

psql "host=${CLUSTER_ENDPOINT} port=5432 user=postgres sslmode=require" <<EOF
CREATE DATABASE ${DB_NAME};
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
\c ${DB_NAME}
GRANT ALL ON SCHEMA public TO ${DB_USER};
EOF

echo ""
echo_info "Database and user created successfully"

# Create Secrets Manager secret
echo_info "Creating Secrets Manager secret: $SECRET_NAME"
aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "Database credentials for ${PROJECT_PREFIX}" \
    --secret-string "{
        \"username\": \"${DB_USER}\",
        \"password\": \"${DB_PASSWORD}\",
        \"host\": \"${CLUSTER_ENDPOINT}\",
        \"port\": \"5432\",
        \"dbname\": \"${DB_NAME}\"
    }" \
    --query 'ARN' \
    --output text

echo ""
echo_info "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run ./scripts/bootstrap-secrets.sh to set up application secrets"
echo "  2. Deploy in shared mode:"
echo "     cd infra && npx cdk deploy --all \\"
echo "       --context shared_infra_prefix=/shared-infra/prod \\"
echo "       --context domain_name=api.${PROJECT_PREFIX}.com \\"
echo "       --context alb_rule_priority=<unique-priority>"
