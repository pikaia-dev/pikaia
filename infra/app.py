#!/usr/bin/env python3
"""
AWS CDK app entry point for Tango infrastructure.
"""

import aws_cdk as cdk

from stacks.media_stack import MediaStack
from stacks.network_stack import NetworkStack

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# Foundation stacks
network = NetworkStack(app, "TangoNetwork", env=env)

# Media stack (S3 + CloudFront + image transformation)
# Configuration via cdk.json or --context flag:
#   cors_origins: CORS allowed origins (default: ["*"])
#   enable_versioning: Enable S3 versioning for data recovery (default: false)
# Example: cdk deploy --context cors_origins='["https://app.yourdomain.com"]' --context enable_versioning=true
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

# TODO: Add more stacks as needed
# database = DatabaseStack(app, "TangoDatabase", vpc=network.vpc, env=env)
# backend = BackendStack(app, "TangoBackend", vpc=network.vpc, env=env)
# frontend = FrontendStack(app, "TangoFrontend", env=env)

app.synth()
