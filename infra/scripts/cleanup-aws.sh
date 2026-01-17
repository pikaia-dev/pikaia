#!/bin/bash
# AWS Resource Cleanup Script
# Removes orphaned resources not managed by CDK
#
# Usage: ./cleanup-aws.sh [--dry-run]
#        AWS_PROFILE=tango-b2b-demo ./cleanup-aws.sh
#
# Prerequisites:
#   - AWS CLI configured (profile or environment credentials)
#   - jq installed

set -euo pipefail

# Use profile if set, otherwise use default/environment credentials (for CI)
if [[ -n "${AWS_PROFILE:-}" ]]; then
    AWS_OPTS="--profile $AWS_PROFILE"
else
    AWS_OPTS=""
fi

DRY_RUN="${1:-}"
KEEP_TASK_DEFINITIONS=5

echo "=== AWS Cleanup Script ==="
echo "Mode: ${DRY_RUN:-live}"
echo ""

# Wrapper for AWS CLI with optional profile
aws_cmd() {
    # shellcheck disable=SC2086
    aws $AWS_OPTS "$@"
}

# Function to run or simulate AWS commands
run_cmd() {
    if [[ "$DRY_RUN" == "--dry-run" ]]; then
        echo "  [DRY-RUN] Would run: aws $AWS_OPTS $*"
    else
        aws_cmd "$@"
    fi
}

# ============================================================
# 1. Clean up orphaned CloudWatch Log Groups
# ============================================================
echo "=== Checking for orphaned CloudWatch Log Groups ==="

# Get all log groups
LOG_GROUPS=$(aws_cmd logs describe-log-groups \
    --query 'logGroups[].logGroupName' --output text)

for LOG_GROUP in $LOG_GROUPS; do
    # Check for RDS log groups from deleted clusters
    if [[ "$LOG_GROUP" == /aws/rds/cluster/* ]]; then
        CLUSTER_ID=$(echo "$LOG_GROUP" | sed 's|/aws/rds/cluster/\([^/]*\)/.*|\1|')

        # Check if cluster exists
        if ! aws_cmd rds describe-db-clusters \
            --db-cluster-identifier "$CLUSTER_ID" &>/dev/null; then
            echo "  Found orphaned RDS log group: $LOG_GROUP"
            run_cmd logs delete-log-group --log-group-name "$LOG_GROUP"
        fi
    fi

    # Check for empty ECS log groups (0 stored bytes)
    if [[ "$LOG_GROUP" == TangoApp-* ]]; then
        STORED_BYTES=$(aws_cmd logs describe-log-groups \
            --log-group-name-prefix "$LOG_GROUP" \
            --query 'logGroups[0].storedBytes' --output text)

        if [[ "$STORED_BYTES" == "0" ]]; then
            echo "  Found empty log group: $LOG_GROUP"
            run_cmd logs delete-log-group --log-group-name "$LOG_GROUP"
        fi
    fi
done

echo ""

# ============================================================
# 2. Deregister old ECS Task Definitions
# ============================================================
echo "=== Cleaning up old ECS Task Definitions ==="
echo "  Keeping latest $KEEP_TASK_DEFINITIONS revisions"

TASK_DEFS=$(aws_cmd ecs list-task-definitions \
    --sort DESC --query 'taskDefinitionArns' --output json)

# Get count and identify old ones
TOTAL=$(echo "$TASK_DEFS" | jq 'length')
TO_DELETE=$(echo "$TASK_DEFS" | jq -r ".[$KEEP_TASK_DEFINITIONS:][]")

if [[ -n "$TO_DELETE" ]]; then
    COUNT=$((TOTAL - KEEP_TASK_DEFINITIONS))
    echo "  Found $COUNT old task definitions to deregister"

    for ARN in $TO_DELETE; do
        REVISION=$(echo "$ARN" | sed 's|.*/||')
        echo "  Deregistering: $REVISION"
        run_cmd ecs deregister-task-definition --task-definition "$ARN" --no-cli-pager >/dev/null
    done
else
    echo "  No old task definitions to clean up"
fi

echo ""

# ============================================================
# 3. Clean up untagged ECR images
# ============================================================
echo "=== Cleaning up untagged ECR images ==="

REPOS=$(aws_cmd ecr describe-repositories \
    --query 'repositories[].repositoryName' --output text)

for REPO in $REPOS; do
    # Skip CDK assets repo
    if [[ "$REPO" == cdk-* ]]; then
        continue
    fi

    UNTAGGED=$(aws_cmd ecr describe-images \
        --repository-name "$REPO" \
        --query 'imageDetails[?imageTags==`null`].imageDigest' --output json)

    COUNT=$(echo "$UNTAGGED" | jq 'length')

    if [[ "$COUNT" -gt 0 ]]; then
        echo "  Found $COUNT untagged images in $REPO"

        # Build image IDs JSON
        IMAGE_IDS=$(echo "$UNTAGGED" | jq '[.[] | {imageDigest: .}]')

        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            aws_cmd ecr batch-delete-image \
                --repository-name "$REPO" \
                --image-ids "$IMAGE_IDS" >/dev/null
            echo "    Deleted $COUNT untagged images"
        else
            echo "  [DRY-RUN] Would delete $COUNT untagged images"
        fi
    else
        echo "  No untagged images in $REPO"
    fi
done

echo ""
echo "=== Cleanup complete ==="
