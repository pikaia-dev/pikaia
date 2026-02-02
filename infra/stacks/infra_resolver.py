"""
Infrastructure resolver for shared vs standalone mode.

This module provides utilities to detect whether the CDK app should create
its own infrastructure (standalone mode) or use shared infrastructure from
SSM parameters (shared mode).

Shared mode is activated by passing --context shared_infra_prefix=/shared-infra/prod

SSM Parameter Structure (created by shared-infra repo):
    /shared-infra/{env}/network/vpc-id
    /shared-infra/{env}/network/private-subnet-ids
    /shared-infra/{env}/network/public-subnet-ids
    /shared-infra/{env}/network/availability-zones
    /shared-infra/{env}/alb/arn
    /shared-infra/{env}/alb/dns-name
    /shared-infra/{env}/alb/security-group-id
    /shared-infra/{env}/alb/https-listener-arn
    /shared-infra/{env}/database/cluster-endpoint
    /shared-infra/{env}/database/security-group-id
    /shared-infra/{env}/database/proxy-endpoint
"""

from dataclasses import dataclass

from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_ssm as ssm
from constructs import Construct


@dataclass
class SharedInfraConfig:
    """Configuration loaded from shared infrastructure SSM parameters."""

    # Network
    vpc_id: str
    private_subnet_ids: list[str]
    public_subnet_ids: list[str]
    availability_zones: list[str]

    # ALB
    alb_arn: str
    alb_dns_name: str
    alb_security_group_id: str
    https_listener_arn: str

    # Database
    database_cluster_endpoint: str
    database_security_group_id: str
    rds_proxy_endpoint: str


class InfraResolver:
    """
    Resolves infrastructure resources - either from shared SSM parameters
    or returns None to signal standalone mode.

    Usage:
        resolver = InfraResolver(app, shared_prefix)

        if resolver.is_shared_mode:
            vpc = resolver.lookup_vpc()
            alb = resolver.lookup_alb()
        else:
            # Create resources normally
            vpc = NetworkStack(...)
    """

    def __init__(self, scope: Construct, shared_prefix: str | None = None) -> None:
        """
        Initialize the resolver.

        Args:
            scope: CDK construct scope (usually the App)
            shared_prefix: SSM parameter prefix (e.g., "/shared-infra/prod")
                          If None, operates in standalone mode.
        """
        self.scope = scope
        self.shared_prefix = shared_prefix
        self._config: SharedInfraConfig | None = None
        self._lookup_scope_counter = 0

    @property
    def is_shared_mode(self) -> bool:
        """Check if operating in shared infrastructure mode."""
        return self.shared_prefix is not None

    def _get_unique_id(self, base: str) -> str:
        """Generate unique construct ID for lookups."""
        self._lookup_scope_counter += 1
        return f"{base}{self._lookup_scope_counter}"

    def _get_ssm_value(self, suffix: str) -> str:
        """
        Look up an SSM parameter value.

        Note: ssm.StringParameter.value_from_lookup is used during synthesis
        to resolve the value. This requires the parameter to exist at synth time.
        """
        if not self.shared_prefix:
            raise RuntimeError("Cannot lookup SSM values in standalone mode")

        parameter_name = f"{self.shared_prefix}/{suffix}"
        return ssm.StringParameter.value_from_lookup(self.scope, parameter_name)

    def get_shared_config(self) -> SharedInfraConfig | None:
        """
        Load shared infrastructure config from SSM parameters.

        Returns None in standalone mode.
        Caches the result for repeated calls.
        """
        if not self.shared_prefix:
            return None

        if self._config is not None:
            return self._config

        self._config = SharedInfraConfig(
            # Network
            vpc_id=self._get_ssm_value("network/vpc-id"),
            private_subnet_ids=self._get_ssm_value("network/private-subnet-ids").split(","),
            public_subnet_ids=self._get_ssm_value("network/public-subnet-ids").split(","),
            availability_zones=self._get_ssm_value("network/availability-zones").split(","),
            # ALB
            alb_arn=self._get_ssm_value("alb/arn"),
            alb_dns_name=self._get_ssm_value("alb/dns-name"),
            alb_security_group_id=self._get_ssm_value("alb/security-group-id"),
            https_listener_arn=self._get_ssm_value("alb/https-listener-arn"),
            # Database
            database_cluster_endpoint=self._get_ssm_value("database/cluster-endpoint"),
            database_security_group_id=self._get_ssm_value("database/security-group-id"),
            rds_proxy_endpoint=self._get_ssm_value("database/proxy-endpoint"),
        )
        return self._config

    def lookup_vpc(self, scope: Construct) -> ec2.IVpc | None:
        """
        Look up VPC from shared infrastructure.

        Returns None in standalone mode.
        """
        config = self.get_shared_config()
        if not config:
            return None

        return ec2.Vpc.from_vpc_attributes(
            scope,
            self._get_unique_id("SharedVpc"),
            vpc_id=config.vpc_id,
            availability_zones=config.availability_zones,
            private_subnet_ids=config.private_subnet_ids,
            public_subnet_ids=config.public_subnet_ids,
        )

    def lookup_alb(self, scope: Construct) -> elbv2.IApplicationLoadBalancer | None:
        """
        Look up ALB from shared infrastructure.

        Returns None in standalone mode.
        """
        config = self.get_shared_config()
        if not config:
            return None

        return elbv2.ApplicationLoadBalancer.from_application_load_balancer_attributes(
            scope,
            self._get_unique_id("SharedAlb"),
            load_balancer_arn=config.alb_arn,
            security_group_id=config.alb_security_group_id,
            load_balancer_dns_name=config.alb_dns_name,
        )

    def lookup_https_listener(self, scope: Construct) -> elbv2.IApplicationListener | None:
        """
        Look up HTTPS listener from shared ALB.

        Returns None in standalone mode.
        """
        config = self.get_shared_config()
        if not config:
            return None

        # Create a security group reference for the listener
        alb_sg = ec2.SecurityGroup.from_security_group_id(
            scope,
            self._get_unique_id("SharedAlbSg"),
            config.alb_security_group_id,
        )

        return elbv2.ApplicationListener.from_application_listener_attributes(
            scope,
            self._get_unique_id("SharedHttpsListener"),
            listener_arn=config.https_listener_arn,
            security_group=alb_sg,
        )

    def lookup_database_security_group(self, scope: Construct) -> ec2.ISecurityGroup | None:
        """
        Look up database security group from shared infrastructure.

        Returns None in standalone mode.
        """
        config = self.get_shared_config()
        if not config:
            return None

        return ec2.SecurityGroup.from_security_group_id(
            scope,
            self._get_unique_id("SharedDbSg"),
            config.database_security_group_id,
        )
