"""
Network stack - VPC, subnets, and security groups.

Supports two modes:
- Standalone: Creates VPC, subnets, and NAT gateway
- Shared: Uses existing VPC from shared infrastructure (pass shared_vpc parameter)
"""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):
    """Creates the foundational VPC and networking components."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        shared_vpc: ec2.IVpc | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Shared mode: use provided VPC without creating resources
        if shared_vpc:
            self.vpc = shared_vpc
            return

        # Get explicit AZs from context if provided (for CI/CD consistency)
        # Pass via: --context availability_zones=us-east-1a,us-east-1b
        az_context = self.node.try_get_context("availability_zones")
        availability_zones = az_context.split(",") if az_context else None

        # VPC with public and private subnets
        # If availability_zones is provided, use those explicitly to avoid
        # CDK lookup caching issues in CI/CD environments
        self.vpc = ec2.Vpc(
            self,
            "PikaiaVpc",
            max_azs=2 if not availability_zones else None,
            availability_zones=availability_zones,
            nat_gateways=1,  # Cost optimization: single NAT for dev
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # Outputs for CI/CD workflow lookups
        private_subnet_ids = [subnet.subnet_id for subnet in self.vpc.private_subnets]
        CfnOutput(
            self,
            "PrivateSubnets",
            value=",".join(private_subnet_ids),
            description="Comma-separated list of private subnet IDs",
        )
