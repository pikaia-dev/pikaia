#!/usr/bin/env python3
"""
AWS CDK app entry point for Tango infrastructure.
"""

import aws_cdk as cdk

from stacks.network_stack import NetworkStack

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# Foundation stacks
network = NetworkStack(app, "TangoNetwork", env=env)

# TODO: Add more stacks as needed
# database = DatabaseStack(app, "TangoDatabase", vpc=network.vpc, env=env)
# backend = BackendStack(app, "TangoBackend", vpc=network.vpc, env=env)
# frontend = FrontendStack(app, "TangoFrontend", env=env)

app.synth()
