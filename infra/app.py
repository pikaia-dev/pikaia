#!/usr/bin/env python3
"""
AWS CDK app entry point for Tango infrastructure.

Stacks:
- TangoNetwork: VPC, subnets, NAT gateway, database security group
- TangoApp: Aurora PostgreSQL, ECS Fargate, ALB, Secrets Manager
- TangoFrontend: S3 + CloudFront for React SPA with API routing
- TangoMedia: S3 bucket, CloudFront CDN, image transformation Lambda
- TangoEvents: EventBridge bus, publisher Lambda, DLQ
- TangoObservability: CloudWatch dashboards and alarms

Usage:
    # Synth (validate)
    cdk synth --all

    # Deploy foundation
    cdk deploy TangoNetwork TangoApp TangoFrontend

    # Deploy with custom domain
    cdk deploy TangoApp --context domain_name=api.example.com --context certificate_arn=arn:aws:acm:...

    # Deploy with alarm notifications
    cdk deploy TangoObservability --context alarm_email=ops@example.com

    # Deploy all
    cdk deploy --all
"""

import aws_cdk as cdk

from stacks.app_stack import AppStack
from stacks.events_stack import EventsStack
from stacks.frontend_stack import FrontendStack
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
# Foundation: Network + Security Groups
# =============================================================================

network = NetworkStack(app, "TangoNetwork", env=env)

# =============================================================================
# Media: S3 + CloudFront + Image Transformation
# Must be created before AppStack so we can pass the bucket
# =============================================================================

# Configuration via cdk.json or --context flag:
#   cors_origins: CORS allowed origins (default: ["*"])
#   enable_versioning: Enable S3 versioning for data recovery (default: false)
# Example: cdk deploy TangoMedia --context cors_origins='["https://app.example.com"]'
cors_origins = app.node.try_get_context("cors_origins") or ["*"]
enable_versioning = app.node.try_get_context("enable_versioning") or False

media = MediaStack(
    app,
    "TangoMedia",
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

app_stack = AppStack(
    app,
    "TangoApp",
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

frontend = FrontendStack(
    app,
    "TangoFrontend",
    alb=app_stack.alb,
    domain_name=frontend_domain,
    certificate_arn=frontend_certificate_arn,
    env=env,
)
frontend.add_dependency(app_stack)

# =============================================================================
# Events: EventBridge + Publisher Lambda + DLQ
# =============================================================================

events_stack = EventsStack(
    app,
    "TangoEvents",
    vpc=network.vpc,
    database_secret=app_stack.database_secret,
    database_security_group=app_stack.database_security_group,
    rds_proxy_endpoint=app_stack.rds_proxy.endpoint,
    event_bus_name="tango-events",
    env=env,
)
events_stack.add_dependency(app_stack)

# =============================================================================
# Observability: CloudWatch Dashboards + Alarms
# =============================================================================

# Optional: Email for alarm notifications
alarm_email = app.node.try_get_context("alarm_email")

observability = ObservabilityStack(
    app,
    "TangoObservability",
    alb=app_stack.alb,
    target_group=app_stack.target_group,
    ecs_cluster=app_stack.cluster,
    ecs_service=app_stack.fargate_service.service,
    database=app_stack.database,
    alarm_email=alarm_email,
    env=env,
)
observability.add_dependency(app_stack)

# =============================================================================
# Validation: Pre-deployment checks
# =============================================================================
# These aspects run during `cdk synth` and add warnings/errors for:
# - Production readiness (HA, deletion protection)
# - Security (S3 public access, encryption)
add_validation_aspects(app)

app.synth()
