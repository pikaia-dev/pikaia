#!/usr/bin/env bash
# Teardown script for demo/staging environments.
# Deletes all CloudFormation stacks and cleans up retained/orphaned resources.
#
# All resource names are derived from infra/cdk.json context values, matching
# the same logic used by CDK when creating resources.
#
# Prerequisites: AWS CLI configured with appropriate credentials, jq installed.
#
# Usage: AWS_REGION=us-east-1 bash scripts/teardown-demo.sh

set -euo pipefail

REGION="${AWS_REGION:?Set AWS_REGION before running this script}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CDK_JSON="${SCRIPT_DIR}/../infra/cdk.json"

if [[ ! -f "${CDK_JSON}" ]]; then
  echo "Error: ${CDK_JSON} not found. Run this script from the project root."
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required. Install it with: brew install jq"
  exit 1
fi

# ─── Read resource naming from cdk.json (same source of truth as CDK) ───────

PREFIX=$(jq -r '.context.resource_prefix // "pikaia"' "${CDK_JSON}")
ECR_REPO=$(jq -r '.context.ecr_repository_name // "pikaia-backend"' "${CDK_JSON}")
SECRETS_PATH=$(jq -r '.context.secrets_path // "pikaia/app-secrets"' "${CDK_JSON}")

# Stack names use title-cased prefix (e.g., "pikaia" → "Pikaia")
STACK_PREFIX="$(echo "${PREFIX:0:1}" | tr '[:lower:]' '[:upper:]')${PREFIX:1}"

# All stacks created by infra/app.py
STACKS=(
  "${STACK_PREFIX}Observability"
  "${STACK_PREFIX}Events"
  "${STACK_PREFIX}Frontend"
  "${STACK_PREFIX}App"
  "${STACK_PREFIX}WafRegional"
  "${STACK_PREFIX}Media"
  "${STACK_PREFIX}Network"
  "${STACK_PREFIX}WafCloudFront"
)

echo "=== Demo Environment Teardown ==="
echo "Region:          ${REGION}"
echo "Resource prefix: ${PREFIX}"
echo "Stack prefix:    ${STACK_PREFIX}"
echo "Stacks to delete: ${STACKS[*]}"
echo ""

# ─── Step 1: Disable RDS deletion protection ────────────────────────────────

echo "--- Step 1: Disable RDS deletion protection ---"

# CloudFormation generates cluster IDs like "{stackname}{logicalid}{hash}" (lowercased)
CLUSTER_ID=$(aws rds describe-db-clusters \
  --region "${REGION}" \
  --query "DBClusters[?starts_with(DBClusterIdentifier, '$(echo "${STACK_PREFIX}App" | tr '[:upper:]' '[:lower:]')')].DBClusterIdentifier | [0]" \
  --output text 2>/dev/null || echo "None")

if [[ "${CLUSTER_ID}" != "None" && -n "${CLUSTER_ID}" ]]; then
  echo "Found RDS cluster: ${CLUSTER_ID}"
  echo "Disabling deletion protection..."
  aws rds modify-db-cluster \
    --region "${REGION}" \
    --db-cluster-identifier "${CLUSTER_ID}" \
    --no-deletion-protection \
    --apply-immediately \
    --output text > /dev/null
  echo "Waiting for cluster to apply changes..."
  aws rds wait db-cluster-available \
    --region "${REGION}" \
    --db-cluster-identifier "${CLUSTER_ID}" 2>/dev/null || true
  echo "Deletion protection disabled."
else
  echo "No RDS cluster found (may already be deleted)."
fi

# ─── Step 2: Empty S3 buckets before stack deletion ──────────────────────────

echo ""
echo "--- Step 2: Empty S3 buckets that block stack deletion ---"

# Media bucket (RemovalPolicy.RETAIN — CloudFormation won't delete it, but we
# empty it now so we can delete it in step 4)
MEDIA_BUCKET=$(aws cloudformation describe-stack-resources \
  --region "${REGION}" \
  --stack-name "${STACK_PREFIX}Media" \
  --query "StackResources[?ResourceType=='AWS::S3::Bucket'].PhysicalResourceId | [0]" \
  --output text 2>/dev/null || echo "None")

if [[ "${MEDIA_BUCKET}" != "None" && -n "${MEDIA_BUCKET}" ]]; then
  echo "Emptying media bucket: ${MEDIA_BUCKET}"
  aws s3 rm "s3://${MEDIA_BUCKET}" --recursive --region "${REGION}" 2>/dev/null || true
  echo "Media bucket emptied."
else
  echo "No media bucket found."
fi

# ─── Step 3: Delete CloudFormation stacks (reverse dependency order) ─────────

echo ""
echo "--- Step 3: Delete CloudFormation stacks ---"

delete_stack() {
  local stack_name=$1
  local region=${2:-${REGION}}
  local status

  status=$(aws cloudformation describe-stacks \
    --region "${region}" \
    --stack-name "${stack_name}" \
    --query "Stacks[0].StackStatus" \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [[ "${status}" == "NOT_FOUND" ]]; then
    echo "  ${stack_name}: already deleted, skipping."
    return 0
  fi

  echo "  ${stack_name}: deleting (was ${status})..."
  aws cloudformation delete-stack \
    --region "${region}" \
    --stack-name "${stack_name}"

  echo "  ${stack_name}: waiting for deletion..."
  if aws cloudformation wait stack-delete-complete \
    --region "${region}" \
    --stack-name "${stack_name}" 2>/dev/null; then
    echo "  ${stack_name}: deleted."
  else
    echo "  ${stack_name}: delete may have failed — check AWS console."
    return 1
  fi
}

# Tier 1 — leaf stacks (no dependents) — delete in parallel
echo "Deleting leaf stacks..."
delete_stack "${STACK_PREFIX}Observability" &
PID_OBS=$!
delete_stack "${STACK_PREFIX}Events" &
PID_EVT=$!
delete_stack "${STACK_PREFIX}Frontend" &
PID_FE=$!

wait ${PID_OBS} ${PID_EVT} ${PID_FE}

# Tier 2 — App (depends on Network, Media, WafRegional)
echo "Deleting ${STACK_PREFIX}App..."
delete_stack "${STACK_PREFIX}App"

# Tier 3 — base stacks (delete in parallel)
# WafCloudFront is always in us-east-1 (CLOUDFRONT scope requirement)
echo "Deleting base stacks..."
delete_stack "${STACK_PREFIX}WafRegional" &
PID_WAF_R=$!
delete_stack "${STACK_PREFIX}Media" &
PID_MEDIA=$!
delete_stack "${STACK_PREFIX}Network" &
PID_NET=$!
delete_stack "${STACK_PREFIX}WafCloudFront" "us-east-1" &
PID_WAF_CF=$!

wait ${PID_WAF_R} ${PID_MEDIA} ${PID_NET} ${PID_WAF_CF}

# ─── Step 4: Clean up retained/orphaned resources ────────────────────────────

echo ""
echo "--- Step 4: Clean up orphaned resources ---"

# Media S3 bucket (RemovalPolicy.RETAIN means CloudFormation left it behind)
if [[ "${MEDIA_BUCKET}" != "None" && -n "${MEDIA_BUCKET}" ]]; then
  echo "Deleting orphaned media bucket: ${MEDIA_BUCKET}"
  # Delete any remaining object versions and delete markers
  aws s3api list-object-versions \
    --region "${REGION}" \
    --bucket "${MEDIA_BUCKET}" \
    --query '{Objects: [].{Key:Key,VersionId:VersionId}}' \
    --output json 2>/dev/null | \
    aws s3api delete-objects \
      --region "${REGION}" \
      --bucket "${MEDIA_BUCKET}" \
      --delete file:///dev/stdin 2>/dev/null || true
  aws s3 rb "s3://${MEDIA_BUCKET}" --region "${REGION}" 2>/dev/null || true
  echo "Media bucket deleted."
fi

# SQS DLQs (RemovalPolicy.RETAIN) — names match events_stack.py
echo "Cleaning up orphaned SQS queues..."
for queue_name in "${PREFIX}-events-publisher-dlq" "${PREFIX}-audit-dlq"; do
  QUEUE_URL=$(aws sqs get-queue-url \
    --region "${REGION}" \
    --queue-name "${queue_name}" \
    --query "QueueUrl" \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [[ "${QUEUE_URL}" != "NOT_FOUND" && -n "${QUEUE_URL}" ]]; then
    echo "  Deleting queue: ${queue_name}"
    aws sqs delete-queue --region "${REGION}" --queue-url "${QUEUE_URL}"
  else
    echo "  Queue ${queue_name} not found, skipping."
  fi
done

# ─── Step 5: Clean up CloudWatch log groups ──────────────────────────────────

echo ""
echo "--- Step 5: Clean up CloudWatch log groups ---"

delete_log_groups() {
  local region=$1
  local prefix=$2
  local groups

  groups=$(aws logs describe-log-groups \
    --region "${region}" \
    --log-group-name-prefix "${prefix}" \
    --query "logGroups[].logGroupName" \
    --output text 2>/dev/null || echo "")

  if [[ -n "${groups}" ]]; then
    for lg in ${groups}; do
      echo "  Deleting log group: ${lg}"
      aws logs delete-log-group --region "${region}" --log-group-name "${lg}" 2>/dev/null || true
    done
  fi
}

# Lambda log groups: /aws/lambda/{prefix}-event-publisher, /aws/lambda/{prefix}-audit-consumer
delete_log_groups "${REGION}" "/aws/lambda/${PREFIX}"

# ECS log groups: stream_prefix from cdk.json log_stream_prefix context
delete_log_groups "${REGION}" "/ecs/${PREFIX}"

# RDS log groups: cluster ID starts with lowercased "{stackprefix}app"
delete_log_groups "${REGION}" "/aws/rds/cluster/$(echo "${STACK_PREFIX}app" | tr '[:upper:]' '[:lower:]')"

# WAF log groups (regional)
delete_log_groups "${REGION}" "aws-waf-logs-${PREFIX}-regional"

# WAF log groups (CloudFront — always in us-east-1)
delete_log_groups "us-east-1" "aws-waf-logs-${PREFIX}-cloudfront"

echo ""
echo "=== Teardown complete ==="
echo ""
echo "Resources preserved (needed for redeployment):"
echo "  - ECR repository: ${ECR_REPO}"
echo "  - Secrets Manager: ${SECRETS_PATH}"
echo "  - CDKToolkit bootstrap stack"
echo ""
echo "To redeploy, re-run the GitHub Actions workflow or:"
echo "  cd infra && cdk deploy --all"
