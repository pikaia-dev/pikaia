"""
Stack to export standalone infrastructure resources as SSM parameters.

When deployed alongside standalone mode, this stack writes the same SSM
parameters that InfraResolver expects in shared mode. This lets a second
deployment of the same repo consume infrastructure from the first without
needing a separate shared-infra repository.

Activated by passing --context export_shared_infra_prefix=/shared-infra/prod
"""

from aws_cdk import Fn, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class SharedExportStack(Stack):
    """Exports standalone resources as SSM parameters for shared mode consumers."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        prefix: str,
        vpc: ec2.IVpc,
        alb: elbv2.IApplicationLoadBalancer,
        alb_security_group: ec2.ISecurityGroup,
        https_listener: elbv2.IApplicationListener,
        database: rds.IDatabaseCluster,
        database_security_group: ec2.ISecurityGroup,
        rds_proxy: rds.IDatabaseProxy,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Network parameters
        ssm.StringParameter(
            self,
            "VpcId",
            parameter_name=f"{prefix}/network/vpc-id",
            string_value=vpc.vpc_id,
        )

        ssm.StringParameter(
            self,
            "PrivateSubnetIds",
            parameter_name=f"{prefix}/network/private-subnet-ids",
            string_value=Fn.join(",", [s.subnet_id for s in vpc.private_subnets]),
        )

        ssm.StringParameter(
            self,
            "PublicSubnetIds",
            parameter_name=f"{prefix}/network/public-subnet-ids",
            string_value=Fn.join(",", [s.subnet_id for s in vpc.public_subnets]),
        )

        ssm.StringParameter(
            self,
            "AvailabilityZones",
            parameter_name=f"{prefix}/network/availability-zones",
            string_value=",".join(vpc.availability_zones),
        )

        # ALB parameters
        ssm.StringParameter(
            self,
            "AlbArn",
            parameter_name=f"{prefix}/alb/arn",
            string_value=alb.load_balancer_arn,
        )

        ssm.StringParameter(
            self,
            "AlbDnsName",
            parameter_name=f"{prefix}/alb/dns-name",
            string_value=alb.load_balancer_dns_name,
        )

        ssm.StringParameter(
            self,
            "AlbSecurityGroupId",
            parameter_name=f"{prefix}/alb/security-group-id",
            string_value=alb_security_group.security_group_id,
        )

        ssm.StringParameter(
            self,
            "HttpsListenerArn",
            parameter_name=f"{prefix}/alb/https-listener-arn",
            string_value=https_listener.listener_arn,
        )

        # Database parameters
        ssm.StringParameter(
            self,
            "DatabaseClusterEndpoint",
            parameter_name=f"{prefix}/database/cluster-endpoint",
            string_value=database.cluster_endpoint.hostname,
        )

        ssm.StringParameter(
            self,
            "DatabaseSecurityGroupId",
            parameter_name=f"{prefix}/database/security-group-id",
            string_value=database_security_group.security_group_id,
        )

        ssm.StringParameter(
            self,
            "RdsProxyEndpoint",
            parameter_name=f"{prefix}/database/proxy-endpoint",
            string_value=rds_proxy.endpoint,
        )
