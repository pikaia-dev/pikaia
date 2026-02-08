"""
Application stack - ECS Fargate, Aurora PostgreSQL, and ALB.

This stack deploys the Django backend with:
- Aurora PostgreSQL Serverless v2 for database
- ECS Fargate for containerized Django app
- Application Load Balancer with HTTPS
- Secrets Manager for sensitive configuration

Supports two modes:
- Standalone: Creates all resources (database, ALB, ECS)
- Shared: Uses shared VPC/ALB/database, creates only ECS service + target group
  Activated by passing shared_* parameters from InfraResolver
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    Fn,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_certificatemanager as acm,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecr as ecr,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_ecs_patterns as ecs_patterns,
)
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_rds as rds,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from constructs import Construct


class AppStack(Stack):
    """
    Creates the full application infrastructure.

    Features:
    - Aurora PostgreSQL Serverless v2 (auto-scaling, cost-effective)
    - ECS Fargate service for Django backend
    - Application Load Balancer with HTTPS
    - Secrets Manager for database credentials and API keys
    - CloudWatch logs and monitoring

    Shared Mode:
    - Uses existing VPC, ALB, and database from shared infrastructure
    - Creates only ECS service, target group, and listener rule
    - Requires domain_name for host-based routing
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        media_bucket: s3.IBucket | None = None,
        media_cdn_domain: str | None = None,
        certificate_arn: str | None = None,
        domain_name: str | None = None,
        min_capacity: int = 2,
        max_capacity: int = 10,
        # WAF
        waf_acl_arn: str | None = None,
        # Shared mode parameters
        shared_alb: elbv2.IApplicationLoadBalancer | None = None,
        shared_https_listener: elbv2.IApplicationListener | None = None,
        shared_database_security_group: ec2.ISecurityGroup | None = None,
        shared_rds_proxy_endpoint: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc
        self._is_shared_mode = shared_alb is not None

        # Resource naming from CDK context (allows customization without code changes)
        resource_prefix = self.node.try_get_context("resource_prefix") or "pikaia"
        ecr_repository_name = self.node.try_get_context("ecr_repository_name") or "pikaia-backend"
        secrets_path = self.node.try_get_context("secrets_path") or "pikaia/app-secrets"
        database_name = self.node.try_get_context("database_name") or "pikaia"
        log_stream_prefix = self.node.try_get_context("log_stream_prefix") or "pikaia-backend"

        # Shared mode: use project-specific database secret path
        database_secret_path = (
            self.node.try_get_context("database_secret_path")
            or f"{resource_prefix}/database-credentials"
        )

        # ALB listener rule priority for shared mode (must be unique per project)
        alb_rule_priority = self.node.try_get_context("alb_rule_priority") or 100

        # =================================================================
        # Database
        # =================================================================

        if self._is_shared_mode:
            # Shared mode: use existing database from shared infrastructure
            # Import project-specific database secret (created by shared-infra admin)
            self.database_secret = secretsmanager.Secret.from_secret_name_v2(
                self,
                "DatabaseSecret",
                secret_name=database_secret_path,
            )
            self.database_security_group = shared_database_security_group
            self.rds_proxy_endpoint = shared_rds_proxy_endpoint
            # No database or RDS proxy objects in shared mode
            self.database = None
            self.rds_proxy = None
        else:
            # Standalone mode: create all database resources
            # Database security group - created here to avoid cyclic dependencies
            # between stacks. Shared with EventsStack via parameter.
            self.database_security_group = ec2.SecurityGroup(
                self,
                "DatabaseSG",
                vpc=vpc,
                description="Security group for Aurora PostgreSQL",
                allow_all_outbound=False,
            )

            # Aurora Serverless v2 cluster
            self.database = rds.DatabaseCluster(
                self,
                "Database",
                engine=rds.DatabaseClusterEngine.aurora_postgres(
                    version=rds.AuroraPostgresEngineVersion.VER_16_4,
                ),
                serverless_v2_min_capacity=0.5,  # 0.5 ACU minimum (cost optimization)
                serverless_v2_max_capacity=4,  # 4 ACU maximum (adjust based on load)
                writer=rds.ClusterInstance.serverless_v2("writer"),
                vpc=vpc,
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                security_groups=[self.database_security_group],
                default_database_name=database_name,
                removal_policy=RemovalPolicy.SNAPSHOT,  # Take snapshot on delete
                deletion_protection=True,  # Prevent accidental deletion
                backup=rds.BackupProps(retention=Duration.days(7)),
                storage_encrypted=True,
                cloudwatch_logs_exports=["postgresql"],
            )

            # Export database secret for other stacks
            self.database_secret = self.database.secret

            # RDS Proxy for Lambda connections (connection pooling)
            # This is required for Lambda functions to efficiently connect to Aurora
            self.rds_proxy = rds.DatabaseProxy(
                self,
                "RdsProxy",
                proxy_target=rds.ProxyTarget.from_cluster(self.database),
                secrets=[self.database.secret],
                vpc=vpc,
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                security_groups=[self.database_security_group],
                require_tls=True,
                idle_client_timeout=Duration.minutes(5),
                max_connections_percent=90,
                max_idle_connections_percent=10,
            )
            self.rds_proxy_endpoint = self.rds_proxy.endpoint

        # =================================================================
        # Application Secrets
        # =================================================================

        # Application secrets (API keys, etc.)
        # Import existing secret instead of creating - prevents CDK from
        # overwriting manually-populated values. The secret must be created
        # via scripts/bootstrap-secrets.sh BEFORE first deployment.
        self.app_secrets = secretsmanager.Secret.from_secret_name_v2(
            self,
            "AppSecrets",
            secret_name=secrets_path,
        )

        # =================================================================
        # ECS Cluster
        # =================================================================

        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

        # ECR repository for Django app - PREREQUISITE: Repository must exist
        # Using from_repository_name to handle retained repositories from previous deployments.
        # The repository should be created via bootstrap-infra.sh before first deployment.
        # If the repository doesn't exist, deployment will fail with image pull errors.
        self.ecr_repository = ecr.Repository.from_repository_name(
            self,
            "BackendRepo",
            repository_name=ecr_repository_name,
        )

        # =================================================================
        # ECS Fargate Service with ALB
        # =================================================================

        # Task definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "BackendTask",
            cpu=512,
            memory_limit_mib=1024,
        )

        # Build environment variables including S3 config if media bucket is provided
        # ALLOWED_HOSTS is set after ALB creation so we can reference its DNS name
        sentry_dsn = self.node.try_get_context("sentry_dsn") or ""

        container_env = {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            # API goes directly to ALB (not through CloudFront), so use standard header
            "PROXY_SSL_HEADER": "X-Forwarded-Proto",
            "SENTRY_DSN": sentry_dsn,
        }
        if media_bucket:
            container_env.update(
                {
                    "USE_S3_STORAGE": "true",
                    "AWS_STORAGE_BUCKET_NAME": media_bucket.bucket_name,
                    "AWS_S3_REGION_NAME": self.region,
                }
            )
            if media_cdn_domain:
                container_env.update(
                    {
                        "AWS_S3_CUSTOM_DOMAIN": media_cdn_domain,
                        "IMAGE_TRANSFORM_URL": f"https://{media_cdn_domain}",
                    }
                )

        # Container
        container = task_definition.add_container(
            "django",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_repository, "latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=log_stream_prefix,
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment=container_env,
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
                "STYTCH_WEBHOOK_SECRET": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STYTCH_WEBHOOK_SECRET",
                ),
                "STRIPE_SECRET_KEY": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STRIPE_SECRET_KEY",
                ),
                "STRIPE_PRICE_ID": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STRIPE_PRICE_ID",
                ),
                "STRIPE_WEBHOOK_SECRET": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STRIPE_WEBHOOK_SECRET",
                ),
                "RESEND_API_KEY": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="RESEND_API_KEY",
                ),
                "CORS_ALLOWED_ORIGINS": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="CORS_ALLOWED_ORIGINS",
                ),
                # WebAuthn / Passkeys configuration
                "WEBAUTHN_RP_ID": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="WEBAUTHN_RP_ID",
                ),
                "WEBAUTHN_RP_NAME": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="WEBAUTHN_RP_NAME",
                ),
                "WEBAUTHN_ORIGIN": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="WEBAUTHN_ORIGIN",
                ),
                # Stytch Trusted Auth Token (for passkey -> Stytch session)
                "STYTCH_TRUSTED_AUTH_PROFILE_ID": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STYTCH_TRUSTED_AUTH_PROFILE_ID",
                ),
                "STYTCH_TRUSTED_AUTH_AUDIENCE": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STYTCH_TRUSTED_AUTH_AUDIENCE",
                ),
                "STYTCH_TRUSTED_AUTH_ISSUER": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="STYTCH_TRUSTED_AUTH_ISSUER",
                ),
                "PASSKEY_JWT_PRIVATE_KEY": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="PASSKEY_JWT_PRIVATE_KEY",
                ),
                "MOBILE_PROVISION_API_KEY": ecs.Secret.from_secrets_manager(
                    self.app_secrets,
                    field="MOBILE_PROVISION_API_KEY",
                ),
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        container.add_port_mappings(ecs.PortMapping(container_port=8000, protocol=ecs.Protocol.TCP))

        # Grant S3 access for media uploads if bucket is provided
        if media_bucket:
            media_bucket.grant_read_write(task_definition.task_role)

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

        # =================================================================
        # ALB & Fargate Service (mode-dependent)
        # =================================================================

        if self._is_shared_mode:
            # Shared mode: create target group and listener rule on shared ALB
            if not domain_name:
                raise ValueError("domain_name is required in shared mode for host-based routing")

            # Create target group for this project
            self.target_group = elbv2.ApplicationTargetGroup(
                self,
                "TargetGroup",
                target_group_name=f"{resource_prefix}-tg",
                vpc=vpc,
                port=8000,
                protocol=elbv2.ApplicationProtocol.HTTP,
                target_type=elbv2.TargetType.IP,
                health_check=elbv2.HealthCheck(
                    path="/api/v1/health",
                    healthy_http_codes="200",
                    interval=Duration.seconds(30),
                    timeout=Duration.seconds(5),
                ),
            )

            # Create ECS service (without ALB pattern)
            self.ecs_service = ecs.FargateService(
                self,
                "Service",
                cluster=self.cluster,
                task_definition=task_definition,
                desired_count=min_capacity,
                security_groups=[ecs_security_group],
                assign_public_ip=False,
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                health_check_grace_period=Duration.seconds(120),
                min_healthy_percent=100,
                max_healthy_percent=200,
                circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            )

            # Enable ECS Exec
            self.ecs_service.node.default_child.enable_execute_command = True

            # Register service with target group
            self.ecs_service.attach_to_application_target_group(self.target_group)

            # Add listener rule for host-based routing
            elbv2.ApplicationListenerRule(
                self,
                "HostRoutingRule",
                listener=shared_https_listener,
                priority=alb_rule_priority,
                conditions=[
                    elbv2.ListenerCondition.host_headers([domain_name]),
                ],
                target_groups=[self.target_group],
            )

            # Allow shared ALB to reach ECS tasks
            ecs_security_group.add_ingress_rule(
                peer=ec2.Peer.security_group_id(
                    shared_alb.connections.security_groups[0].security_group_id
                ),
                connection=ec2.Port.tcp(8000),
                description="Allow shared ALB to reach ECS",
            )

            # Store shared ALB reference
            self.alb = shared_alb
            self.https_listener = None

            # Auto-scaling
            scaling = self.ecs_service.auto_scale_task_count(
                min_capacity=min_capacity,
                max_capacity=max_capacity,
            )

        else:
            # Standalone mode: create full ALB with ApplicationLoadBalancedFargateService
            if certificate_arn:
                certificate = acm.Certificate.from_certificate_arn(
                    self, "Certificate", certificate_arn
                )
                listener_protocol = elbv2.ApplicationProtocol.HTTPS
            else:
                certificate = None
                listener_protocol = elbv2.ApplicationProtocol.HTTP

            self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
                self,
                "BackendService",
                cluster=self.cluster,
                task_definition=task_definition,
                desired_count=min_capacity,
                security_groups=[ecs_security_group],
                assign_public_ip=False,
                task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                certificate=certificate,
                protocol=listener_protocol,
                # Disable HTTP→HTTPS redirect on ALB since CloudFront handles
                # HTTPS termination and connects to ALB via its domain name
                redirect_http=False,
                health_check_grace_period=Duration.seconds(120),
                min_healthy_percent=100,
                max_healthy_percent=200,
                circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            )

            # Enable ECS Exec for debugging and running migrations
            self.fargate_service.service.node.default_child.enable_execute_command = True

            # Store references
            self.alb = self.fargate_service.load_balancer
            self.target_group = self.fargate_service.target_group
            self.ecs_service = self.fargate_service.service
            self.https_listener = self.fargate_service.listener if certificate_arn else None

            # Health check configuration
            self.target_group.configure_health_check(
                path="/api/v1/health",
                healthy_http_codes="200",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
            )

            # Auto-scaling
            scaling = self.ecs_service.auto_scale_task_count(
                min_capacity=min_capacity,
                max_capacity=max_capacity,
            )

        # =================================================================
        # WAF Association (standalone mode only)
        # =================================================================
        # In shared mode the ALB is managed externally and WAF should be
        # configured in the shared infrastructure stack.

        if waf_acl_arn and not self._is_shared_mode:
            wafv2.CfnWebACLAssociation(
                self,
                "AlbWafAssociation",
                resource_arn=self.alb.load_balancer_arn,
                web_acl_arn=waf_acl_arn,
            )

        # =================================================================
        # ALLOWED_HOSTS (both modes, after ALB is available)
        # =================================================================

        # Build explicit ALLOWED_HOSTS: API domain (if provided) and
        # localhost (for container health checks).
        # In dedicated mode, also include the ALB DNS for ALB health checks.
        # In shared mode, self.alb is an imported resource so we avoid
        # referencing load_balancer_dns_name which may not resolve.
        allowed_hosts_parts = ["localhost"]
        if domain_name:
            allowed_hosts_parts.append(domain_name)
        if not self._is_shared_mode:
            allowed_hosts = Fn.join(
                ",",
                [*allowed_hosts_parts, self.alb.load_balancer_dns_name],
            )
        else:
            allowed_hosts = ",".join(allowed_hosts_parts)
        container.add_environment("ALLOWED_HOSTS", allowed_hosts)

        # ECS Exec permissions (both modes)
        task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ssmmessages:CreateControlChannel",
                    "ssmmessages:CreateDataChannel",
                    "ssmmessages:OpenControlChannel",
                    "ssmmessages:OpenDataChannel",
                ],
                resources=["*"],
            )
        )

        # Auto-scaling policies (both modes)
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

        # =================================================================
        # Outputs
        # =================================================================

        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self.alb.load_balancer_dns_name,
            description="Application Load Balancer DNS name",
            export_name=f"{resource_prefix.title()}ApiDns",
        )

        # Database outputs (standalone mode only)
        if not self._is_shared_mode:
            CfnOutput(
                self,
                "DatabaseEndpoint",
                value=self.database.cluster_endpoint.hostname,
                description="Aurora cluster endpoint",
                export_name=f"{resource_prefix.title()}DatabaseEndpoint",
            )

            CfnOutput(
                self,
                "RdsProxyEndpoint",
                value=self.rds_proxy.endpoint,
                description="RDS Proxy endpoint for Lambda connections",
                export_name=f"{resource_prefix.title()}RdsProxyEndpoint",
            )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=self.database_secret.secret_arn,
            description="Database credentials secret ARN",
            export_name=f"{resource_prefix.title()}DatabaseSecretArn",
        )

        CfnOutput(
            self,
            "AppSecretsArn",
            value=self.app_secrets.secret_arn,
            description="Application secrets ARN (update with API keys)",
            export_name=f"{resource_prefix.title()}AppSecretsArn",
        )

        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=self.ecr_repository.repository_uri,
            description="ECR repository URI for Docker images",
            export_name=f"{resource_prefix.title()}BackendEcrUri",
        )

        # Outputs for CI/CD workflow lookups
        CfnOutput(
            self,
            "ClusterName",
            value=self.cluster.cluster_name,
            description="ECS cluster name",
        )

        CfnOutput(
            self,
            "ServiceName",
            value=self.ecs_service.service_name,
            description="ECS service name",
        )

        CfnOutput(
            self,
            "TaskDefinitionFamily",
            value=task_definition.family,
            description="ECS task definition family name",
        )

        CfnOutput(
            self,
            "EcsSecurityGroup",
            value=self.ecs_service.connections.security_groups[0].security_group_id,
            description="ECS service security group ID",
        )
