#!/usr/bin/env python3
"""
AWS CDK app entry point for Pikaia infrastructure.

Stacks:
- PikaiaNetwork: VPC, subnets, NAT gateway, database security group
- PikaiaApp: Aurora PostgreSQL, ECS Fargate, ALB, Secrets Manager
- PikaiaFrontend: S3 + CloudFront for React SPA with API routing
- PikaiaMedia: S3 bucket, CloudFront CDN, image transformation Lambda
- PikaiaEvents: EventBridge bus, publisher Lambda, DLQ
- PikaiaObservability: CloudWatch dashboards and alarms

Modes:
- Standalone (default): Creates all infrastructure
- Shared: Uses VPC, ALB, and database from shared infrastructure via SSM

Usage:
    # Synth (validate)
    cdk synth --all

    # Deploy foundation (development - HTTP allowed)
    cdk deploy PikaiaNetwork PikaiaApp PikaiaFrontend

    # Deploy for production (HTTPS required)
    cdk deploy --all \\
        --context require_https=true \\
        --context certificate_arn=arn:aws:acm:... \\
        --context cors_origins='["https://app.example.com"]'

    # Deploy with custom domain
    cdk deploy PikaiaApp --context domain_name=api.example.com --context certificate_arn=arn:aws:acm:...

    # Deploy with alarm notifications
    cdk deploy PikaiaObservability --context alarm_email=ops@example.com

    # Deploy in SHARED MODE (uses shared VPC, ALB, database from SSM)
    cdk deploy --all \\
        --context shared_infra_prefix=/shared-infra/prod \\
        --context domain_name=api.pikaia.dev \\
        --context alb_rule_priority=100
"""

import aws_cdk as cdk

from stacks.app_stack import AppStack
from stacks.events_stack import EventsStack
from stacks.frontend_stack import FrontendStack
from stacks.infra_resolver import InfraResolver
from stacks.media_stack import MediaStack
from stacks.network_stack import NetworkStack
from stacks.observability_stack import ObservabilityStack
from stacks.validation import add_validation_aspects

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# =============================================================================
# Shared Infrastructure Detection
# =============================================================================
# If shared_infra_prefix is set, use shared VPC/ALB/database from SSM parameters
# Otherwise, create all resources in standalone mode

shared_infra_prefix = app.node.try_get_context("shared_infra_prefix")
resolver = InfraResolver(app, shared_infra_prefix)

# =============================================================================
# Foundation: Network + Security Groups
# =============================================================================

if resolver.is_shared_mode:
    # Shared mode: look up VPC from SSM parameters
    # NetworkStack is still created but just wraps the shared VPC
    shared_vpc = resolver.lookup_vpc(app)
    network = NetworkStack(app, "PikaiaNetwork", shared_vpc=shared_vpc, env=env)
else:
    # Standalone mode: create VPC and networking
    network = NetworkStack(app, "PikaiaNetwork", env=env)

# =============================================================================
# Media: S3 + CloudFront + Image Transformation
# Must be created before AppStack so we can pass the bucket
# =============================================================================

# Configuration via cdk.json or --context flag:
#   app_domain: App domain for CORS (e.g., "app.example.com") - constructs https:// origin
#   enable_versioning: Enable S3 versioning for data recovery (default: false)
#   require_https: Enforce HTTPS/certificate for production (default: false)
# Example: cdk deploy PikaiaMedia --context app_domain=app.example.com
app_domain = app.node.try_get_context("app_domain")
if app_domain:
    cors_origins = [f"https://{app_domain}"]
else:
    cors_origins = ["*"]
enable_versioning = app.node.try_get_context("enable_versioning") or False
require_https = app.node.try_get_context("require_https") or False

# Validate CORS configuration for production
if require_https and cors_origins == ["*"]:
    raise ValueError(
        "app_domain must be set when require_https=true. "
        "Pass --context app_domain=app.example.com"
    )

media = MediaStack(
    app,
    "PikaiaMedia",
    cors_allowed_origins=cors_origins,
    enable_versioning=enable_versioning,
    enable_image_transformation=True,
    env=env,
)

# =============================================================================
# Application: Database + ECS + ALB
# =============================================================================

# Context parameters for production deployment
domain_name = app.node.try_get_context("domain_name")
certificate_arn = app.node.try_get_context("certificate_arn")

# Validate HTTPS configuration
if domain_name and not certificate_arn:
    raise ValueError(
        "certificate_arn is required when domain_name is provided. "
        "Create a certificate in ACM and pass --context certificate_arn=arn:aws:acm:..."
    )

if require_https and not certificate_arn:
    raise ValueError(
        "certificate_arn is required when require_https=true. "
        "For production deployments, always use HTTPS."
    )

if resolver.is_shared_mode:
    # Shared mode: pass shared infrastructure resources
    shared_config = resolver.get_shared_config()
    app_stack = AppStack(
        app,
        "PikaiaApp",
        vpc=network.vpc,
        media_bucket=media.bucket,
        media_cdn_domain=media.distribution.distribution_domain_name,
        domain_name=domain_name,
        # Shared infrastructure resources
        shared_alb=resolver.lookup_alb(app),
        shared_https_listener=resolver.lookup_https_listener(app),
        shared_database_security_group=resolver.lookup_database_security_group(app),
        shared_rds_proxy_endpoint=shared_config.rds_proxy_endpoint if shared_config else None,
        min_capacity=2,
        max_capacity=10,
        env=env,
    )
else:
    # Standalone mode: create all resources
    app_stack = AppStack(
        app,
        "PikaiaApp",
        vpc=network.vpc,
        media_bucket=media.bucket,
        media_cdn_domain=media.distribution.distribution_domain_name,
        domain_name=domain_name,
        certificate_arn=certificate_arn,
        min_capacity=2,
        max_capacity=10,
        env=env,
    )
app_stack.add_dependency(network)
app_stack.add_dependency(media)

# =============================================================================
# Frontend: S3 + CloudFront for React SPA
# =============================================================================

# Context parameters for custom domain
frontend_domain = app.node.try_get_context("frontend_domain")
frontend_certificate_arn = app.node.try_get_context("frontend_certificate_arn")

if resolver.is_shared_mode:
    # Shared mode: pass ALB DNS name and API domain for HTTPS origin
    shared_config = resolver.get_shared_config()
    frontend = FrontendStack(
        app,
        "PikaiaFrontend",
        alb_dns_name=shared_config.alb_dns_name if shared_config else None,
        api_domain=domain_name,  # Use API domain for HTTPS connection to ALB
        domain_name=frontend_domain,
        certificate_arn=frontend_certificate_arn,
        env=env,
    )
else:
    # Standalone mode: pass ALB object and API domain for HTTPS origin
    frontend = FrontendStack(
        app,
        "PikaiaFrontend",
        alb=app_stack.alb,
        api_domain=domain_name,  # Use API domain for HTTPS connection to ALB
        domain_name=frontend_domain,
        certificate_arn=frontend_certificate_arn,
        env=env,
    )
frontend.add_dependency(app_stack)

# =============================================================================
# Events: EventBridge + Publisher Lambda + DLQ
# =============================================================================

# Events stack works in both modes - it uses the database secret and security group
# which are available from app_stack in both standalone and shared modes
events_stack = EventsStack(
    app,
    "PikaiaEvents",
    vpc=network.vpc,
    database_secret=app_stack.database_secret,
    database_security_group=app_stack.database_security_group,
    rds_proxy_endpoint=app_stack.rds_proxy_endpoint,
    env=env,
)
events_stack.add_dependency(app_stack)

# =============================================================================
# Observability: CloudWatch Dashboards + Alarms
# =============================================================================

# Optional: Email for alarm notifications
alarm_email = app.node.try_get_context("alarm_email")

# Observability stack - database is optional (None in shared mode)
observability = ObservabilityStack(
    app,
    "PikaiaObservability",
    alb=app_stack.alb,
    target_group=app_stack.target_group,
    ecs_cluster=app_stack.cluster,
    ecs_service=app_stack.ecs_service,
    database=app_stack.database,  # None in shared mode
    event_bus=events_stack.event_bus,
    publisher_lambda=events_stack.publisher_lambda,
    audit_lambda=events_stack.audit_lambda,
    alarm_email=alarm_email,
    env=env,
)
observability.add_dependency(app_stack)
observability.add_dependency(events_stack)

# =============================================================================
# Validation: Pre-deployment checks
# =============================================================================
# These aspects run during `cdk synth` and add warnings/errors for:
# - Production readiness (HA, deletion protection)
# - Security (S3 public access, encryption)
add_validation_aspects(app)

app.synth()
