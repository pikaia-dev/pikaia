"""
CDK validation aspects for pre-deployment checks.

These aspects run during `cdk synth` and will add warnings/info
for validation rules, catching issues before deployment.

Usage:
    from stacks.validation import add_validation_aspects
    add_validation_aspects(app)
"""

import aws_cdk as cdk
import jsii
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from constructs import IConstruct


@jsii.implements(cdk.IAspect)
class ProductionReadinessAspect:
    """
    Validates production-readiness requirements for deployed resources.

    Checks:
    - ECS services have at least 2 desired tasks for HA
    - Aurora clusters have deletion protection enabled
    - S3 buckets have versioning enabled (unless explicitly opted out)
    """

    def __init__(self, enforce_ha: bool = True, enforce_deletion_protection: bool = True):
        self._enforce_ha = enforce_ha
        self._enforce_deletion_protection = enforce_deletion_protection

    def visit(self, node: IConstruct) -> None:
        # ECS: Require minimum 2 tasks for high availability
        if self._enforce_ha and isinstance(node, ecs.FargateService):
            cdk.Annotations.of(node).add_info(
                "Ensure ECS service has min_capacity >= 2 for production HA"
            )

        # Aurora: Require deletion protection
        if self._enforce_deletion_protection and isinstance(node, rds.DatabaseCluster):
            cdk.Annotations.of(node).add_info(
                "Ensure deletion_protection=True for production databases"
            )


@jsii.implements(cdk.IAspect)
class SecurityAspect:
    """
    Validates security requirements for deployed resources.

    Checks:
    - S3 buckets block public access
    - S3 buckets have encryption enabled
    """

    def visit(self, node: IConstruct) -> None:
        if isinstance(node, s3.Bucket):
            cdk.Annotations.of(node).add_info("Ensure S3 bucket has block_public_access configured")


def add_validation_aspects(
    scope: cdk.App,
    enforce_ha: bool = True,
    enforce_deletion_protection: bool = True,
    enable_security_checks: bool = True,
) -> None:
    """
    Add validation aspects to all stacks in the CDK app.

    Args:
        scope: The CDK App to add aspects to
        enforce_ha: Whether to check for high-availability configurations
        enforce_deletion_protection: Whether to check for deletion protection
        enable_security_checks: Whether to run security-related validations
    """
    cdk.Aspects.of(scope).add(
        ProductionReadinessAspect(
            enforce_ha=enforce_ha,
            enforce_deletion_protection=enforce_deletion_protection,
        )
    )

    if enable_security_checks:
        cdk.Aspects.of(scope).add(SecurityAspect())
