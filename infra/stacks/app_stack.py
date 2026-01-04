"""
Application stack - ECS Fargate, Aurora PostgreSQL, and ALB.

This stack deploys the Django backend with:
- Aurora PostgreSQL Serverless v2 for database
- ECS Fargate for containerized Django app
- Application Load Balancer with HTTPS
- Secrets Manager for sensitive configuration
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_certificatemanager as acm,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

import json


class AppStack(Stack):
    """
    Creates the full application infrastructure.

    Features:
    - Aurora PostgreSQL Serverless v2 (auto-scaling, cost-effective)
    - ECS Fargate service for Django backend
    - Application Load Balancer with HTTPS
    - Secrets Manager for database credentials and API keys
    - CloudWatch logs and monitoring
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        database_security_group: ec2.ISecurityGroup,
        certificate_arn: str | None = None,
        domain_name: str | None = None,
        min_capacity: int = 2,
        max_capacity: int = 10,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc

        # =================================================================
        # Database
        # =================================================================

        # Security group from NetworkStack (avoids cyclic dependencies)
        self.database_security_group = database_security_group

        # Aurora Serverless v2 cluster
        self.database = rds.DatabaseCluster(
            self,
            "TangoDatabase",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_4,
            ),
            serverless_v2_min_capacity=0.5,  # 0.5 ACU minimum (cost optimization)
            serverless_v2_max_capacity=4,  # 4 ACU maximum (adjust based on load)
            writer=rds.ClusterInstance.serverless_v2("writer"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.database_security_group],
            default_database_name="tango",
            removal_policy=RemovalPolicy.SNAPSHOT,  # Take snapshot on delete
            deletion_protection=True,  # Prevent accidental deletion
            backup=rds.BackupProps(retention=Duration.days(7)),
            storage_encrypted=True,
            cloudwatch_logs_exports=["postgresql"],
        )

        # Export database secret for other stacks
        self.database_secret = self.database.secret

        # =================================================================
        # Application Secrets
        # =================================================================

        # Application secrets (API keys, etc.)
        # Template for app secrets (will be populated post-deployment)
        app_secrets_template = {
            "STYTCH_PROJECT_ID": "",
            "STYTCH_SECRET": "",
            "STRIPE_SECRET_KEY": "",
            "STRIPE_PRICE_ID": "",
        }

        self.app_secrets = secretsmanager.Secret(
            self,
            "AppSecrets",
            secret_name="tango/app-secrets",
            description="Application secrets (Stytch, Stripe, etc.)",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps(app_secrets_template),
                generate_string_key="DJANGO_SECRET_KEY",
                exclude_punctuation=True,
            ),
        )

        # =================================================================
        # ECS Cluster
        # =================================================================

        self.cluster = ecs.Cluster(
            self,
            "TangoCluster",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

        # ECR repository for Django app (import existing or create new)
        # Using from_repository_name to handle retained repositories from previous deployments
        self.ecr_repository = ecr.Repository.from_repository_name(
            self,
            "TangoBackendRepo",
            repository_name="tango-backend",
        )

        # =================================================================
        # ECS Fargate Service with ALB
        # =================================================================

        # Task definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TangoBackendTask",
            cpu=512,
            memory_limit_mib=1024,
        )

        # Container
        container = task_definition.add_container(
            "django",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_repository, "latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="tango-backend",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment={
                "DJANGO_SETTINGS_MODULE": "config.settings.production",
                "ALLOWED_HOSTS": domain_name or "*",
            },
            secrets={
                # RDS secret contains individual fields, not DATABASE_URL.
                # Django settings should construct the URL from these at runtime.
                "DB_HOST": ecs.Secret.from_secrets_manager(
                    self.database_secret,
                    field="host",
                ),
                "DB_PORT": ecs.Secret.from_secrets_manager(
                    self.database_secret,
                    field="port",
                ),
                "DB_NAME": ecs.Secret.from_secrets_manager(
                    self.database_secret,
                    field="dbname",
                ),
                "DB_USER": ecs.Secret.from_secrets_manager(
                    self.database_secret,
                    field="username",
                ),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(
                    self.database_secret,
                    field="password",
                ),
                "SECRET_KEY": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="DJANGO_SECRET_KEY",
                ),
                "STYTCH_PROJECT_ID": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STYTCH_PROJECT_ID",
                ),
                "STYTCH_SECRET": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STYTCH_SECRET",
                ),
                "STRIPE_SECRET_KEY": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STRIPE_SECRET_KEY",
                ),
                "STRIPE_PRICE_ID": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STRIPE_PRICE_ID",
                ),
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        container.add_port_mappings(
            ecs.PortMapping(container_port=8000, protocol=ecs.Protocol.TCP)
        )

        # Security group for ECS
        ecs_security_group = ec2.SecurityGroup(
            self,
            "EcsServiceSG",
            vpc=vpc,
            description="Security group for ECS service",
            allow_all_outbound=True,
        )

        # Allow ECS to connect to database
        # Use CfnSecurityGroupIngress to avoid cross-stack cyclic dependencies
        ec2.CfnSecurityGroupIngress(
            self,
            "EcsToDbIngress",
            ip_protocol="tcp",
            from_port=5432,
            to_port=5432,
            group_id=self.database_security_group.security_group_id,
            source_security_group_id=ecs_security_group.security_group_id,
            description="Allow ECS to connect to Aurora",
        )

        # ALB configuration
        if certificate_arn:
            certificate = acm.Certificate.from_certificate_arn(
                self, "Certificate", certificate_arn
            )
            listener_protocol = elbv2.ApplicationProtocol.HTTPS
        else:
            certificate = None
            listener_protocol = elbv2.ApplicationProtocol.HTTP

        # Fargate service with ALB
        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "TangoBackendService",
            cluster=self.cluster,
            task_definition=task_definition,
            desired_count=min_capacity,
            security_groups=[ecs_security_group],
            assign_public_ip=False,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            certificate=certificate,
            protocol=listener_protocol,
            redirect_http=certificate is not None,
            health_check_grace_period=Duration.seconds(120),
            min_healthy_percent=100,  # Keep all tasks running during deployment
            max_healthy_percent=200,  # Allow 2x tasks during rolling update
        )

        # Auto-scaling
        scaling = self.fargate_service.service.auto_scale_task_count(
            min_capacity=min_capacity,
            max_capacity=max_capacity,
        )

        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        # Health check configuration
        self.fargate_service.target_group.configure_health_check(
            path="/api/v1/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
        )

        # =================================================================
        # Outputs
        # =================================================================

        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self.fargate_service.load_balancer.load_balancer_dns_name,
            description="Application Load Balancer DNS name",
            export_name="TangoApiDns",
        )

        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=self.database.cluster_endpoint.hostname,
            description="Aurora cluster endpoint",
            export_name="TangoDatabaseEndpoint",
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=self.database_secret.secret_arn,
            description="Database credentials secret ARN",
            export_name="TangoDatabaseSecretArn",
        )

        CfnOutput(
            self,
            "AppSecretsArn",
            value=self.app_secrets.secret_arn,
            description="Application secrets ARN (update with API keys)",
            export_name="TangoAppSecretsArn",
        )

        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=self.ecr_repository.repository_uri,
            description="ECR repository URI for Docker images",
            export_name="TangoBackendEcrUri",
        )
