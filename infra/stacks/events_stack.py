"""
Events stack - EventBridge, Publisher Lambda, and Dead Letter Queue.

This stack implements the event publishing infrastructure:
- Custom EventBridge bus for domain events
- Lambda function to poll outbox and publish events
- Audit consumer Lambda for creating audit logs from events
- Dead Letter Queue for failed event delivery
- CloudWatch scheduled rule for fallback polling

Maintenance:
    When adding new audit-worthy event types:
    1. Update AUDIT_EVENT_TYPES in backend/apps/events/management/commands/generate_audit_schema.py
    2. Run: uv run python manage.py generate_audit_schema
    3. Update AUDIT_EVENT_TYPES below to match
    4. CI validates the generated schema; CDK list is validated at synth time
"""

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    aws_sqs as sqs,
)
from constructs import Construct

# Path to Lambda functions directory
FUNCTIONS_DIR = Path(__file__).parent.parent / "functions"

# Lambda runtime versions (centralized for easier upgrades)
PYTHON_RUNTIME = lambda_.Runtime.PYTHON_3_14

# Audit-worthy event types for EventBridge routing.
# IMPORTANT: Keep in sync with AUDIT_EVENT_TYPES in:
#   backend/apps/events/management/commands/generate_audit_schema.py
# The generate_audit_schema command is the single source of truth.
AUDIT_EVENT_TYPES = [
    "member.bulk_invited",
    "member.invited",
    "member.joined",
    "member.removed",
    "member.role_changed",
    "organization.billing_updated",
    "organization.created",
    "organization.updated",
    "user.phone_changed",
    "user.profile_updated",
]


def _create_python_lambda(
    scope: Construct,
    construct_id: str,
    *,
    function_name: str,
    handler: str,
    code_path: Path,
    vpc: ec2.IVpc,
    security_groups: list[ec2.ISecurityGroup],
    environment: dict[str, str],
    timeout_seconds: int = 30,
    memory_size: int = 256,
    description: str = "",
    dead_letter_queue: sqs.IQueue | None = None,
    retry_attempts: int | None = None,
    reserved_concurrent_executions: int | None = None,
) -> lambda_.Function:
    """
    Create a Python Lambda function with standard configuration.

    Centralizes common Lambda settings: VPC, bundling, logging.
    """
    log_group = logs.LogGroup(
        scope,
        f"{construct_id}Logs",
        retention=logs.RetentionDays.ONE_MONTH,
    )

    return lambda_.Function(
        scope,
        construct_id,
        function_name=function_name,
        runtime=PYTHON_RUNTIME,
        handler=handler,
        code=lambda_.Code.from_asset(
            str(code_path),
            exclude=["tests", "__pycache__", "*.pyc"],
            bundling={
                "image": PYTHON_RUNTIME.bundling_image,
                "command": [
                    "bash",
                    "-c",
                    "pip install -r requirements.txt -t /asset-output && cp -r . /asset-output/",
                ],
            },
        ),
        vpc=vpc,
        vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        security_groups=security_groups,
        timeout=Duration.seconds(timeout_seconds),
        memory_size=memory_size,
        dead_letter_queue=dead_letter_queue,
        retry_attempts=retry_attempts,
        reserved_concurrent_executions=reserved_concurrent_executions,
        environment=environment,
        log_group=log_group,
        description=description,
    )


class EventsStack(Stack):
    """
    Creates event publishing infrastructure.

    Features:
    - Custom EventBridge bus for domain events
    - Lambda publisher with VPC access for database connectivity
    - Audit consumer Lambda for audit log creation
    - SQS Dead Letter Queue for failed events
    - CloudWatch scheduled rule for fallback polling
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        database_secret: secretsmanager.ISecret,
        database_security_group: ec2.ISecurityGroup,
        rds_proxy_endpoint: str,
        event_bus_name: str = "tango-events",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc
        self.database_secret = database_secret
        self.rds_proxy_endpoint = rds_proxy_endpoint

        # EventBridge bus for domain events
        self.event_bus = events.EventBus(
            self,
            "TangoEventBus",
            event_bus_name=event_bus_name,
        )

        # Dead Letter Queue for failed event publishing
        self.dlq = sqs.Queue(
            self,
            "EventPublisherDLQ",
            queue_name="tango-events-publisher-dlq",
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Security group for Lambda (needs to access RDS)
        self.lambda_security_group = ec2.SecurityGroup(
            self,
            "EventPublisherSG",
            vpc=vpc,
            description="Security group for event publisher Lambda",
            allow_all_outbound=True,
        )

        # Allow Lambda to connect to database
        # Use CfnSecurityGroupIngress to avoid cross-stack cyclic dependencies
        ec2.CfnSecurityGroupIngress(
            self,
            "LambdaToDbIngress",
            ip_protocol="tcp",
            from_port=5432,
            to_port=5432,
            group_id=database_security_group.security_group_id,
            source_security_group_id=self.lambda_security_group.security_group_id,
            description="Allow event publisher Lambda to connect to RDS",
        )

        # Publisher Lambda function
        self.publisher_lambda = _create_python_lambda(
            self,
            "EventPublisher",
            function_name="tango-event-publisher",
            handler="handler.handler",
            code_path=FUNCTIONS_DIR / "event-publisher",
            vpc=vpc,
            security_groups=[self.lambda_security_group],
            timeout_seconds=60,
            reserved_concurrent_executions=5,  # Limit concurrency to prevent DB overload
            dead_letter_queue=self.dlq,
            environment={
                "EVENT_BUS_NAME": self.event_bus.event_bus_name,
                "BATCH_SIZE": "100",
                "MAX_ATTEMPTS": "10",
            },
            description="Publishes events from outbox table to EventBridge",
        )

        # Grant permissions
        self.event_bus.grant_put_events_to(self.publisher_lambda)
        database_secret.grant_read(self.publisher_lambda)

        # Add DATABASE_URL from secret (assumes secret has standard RDS format)
        # For Aurora Serverless, construct from secret fields
        self.publisher_lambda.add_environment(
            "DATABASE_SECRET_ARN", database_secret.secret_arn
        )

        # CloudWatch scheduled rule for fallback polling
        # This ensures events are published even if Aurora triggers fail
        events.Rule(
            self,
            "EventPublisherSchedule",
            rule_name="tango-event-publisher-schedule",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[events_targets.LambdaFunction(self.publisher_lambda)],
            description="Fallback polling for event publisher",
        )

        # =================================================================
        # Audit Consumer Lambda
        # =================================================================

        # Dead Letter Queue for failed audit events
        self.audit_dlq = sqs.Queue(
            self,
            "AuditDLQ",
            queue_name="tango-audit-dlq",
            retention_period=Duration.days(14),  # Retain for investigation
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Security group for audit Lambda
        audit_lambda_sg = ec2.SecurityGroup(
            self,
            "AuditLambdaSG",
            vpc=vpc,
            description="Security group for audit consumer Lambda",
            allow_all_outbound=True,
        )

        # Allow audit Lambda to connect to database via RDS Proxy
        ec2.CfnSecurityGroupIngress(
            self,
            "AuditLambdaToDbIngress",
            ip_protocol="tcp",
            from_port=5432,
            to_port=5432,
            group_id=database_security_group.security_group_id,
            source_security_group_id=audit_lambda_sg.security_group_id,
            description="Allow audit Lambda to connect via RDS Proxy",
        )

        # Audit consumer Lambda function
        self.audit_lambda = _create_python_lambda(
            self,
            "AuditConsumer",
            function_name="tango-audit-consumer",
            handler="handler.handler",
            code_path=FUNCTIONS_DIR / "audit-consumer",
            vpc=vpc,
            security_groups=[audit_lambda_sg],
            dead_letter_queue=self.audit_dlq,
            retry_attempts=2,  # Retry twice before DLQ
            environment={
                "DATABASE_SECRET_ARN": database_secret.secret_arn,
                "RDS_PROXY_HOST": rds_proxy_endpoint,
            },
            description="Creates audit logs from domain events via EventBridge",
        )

        # Grant Lambda read access to database secret
        database_secret.grant_read(self.audit_lambda)

        # EventBridge rule for audit-worthy events
        events.Rule(
            self,
            "AuditEventRule",
            rule_name="tango-audit-event-rule",
            event_bus=self.event_bus,
            event_pattern=events.EventPattern(
                detail_type=AUDIT_EVENT_TYPES,
            ),
            targets=[
                events_targets.LambdaFunction(
                    self.audit_lambda,
                    dead_letter_queue=self.audit_dlq,  # DLQ for EventBridge delivery failures
                    retry_attempts=3,
                )
            ],
            description="Routes audit-worthy events to audit consumer Lambda",
        )

        # Outputs
        CfnOutput(
            self,
            "EventBusName",
            value=self.event_bus.event_bus_name,
            description="EventBridge bus name for domain events",
            export_name="TangoEventBusName",
        )

        CfnOutput(
            self,
            "EventBusArn",
            value=self.event_bus.event_bus_arn,
            description="EventBridge bus ARN",
            export_name="TangoEventBusArn",
        )

        CfnOutput(
            self,
            "DLQUrl",
            value=self.dlq.queue_url,
            description="Dead Letter Queue URL for failed events",
            export_name="TangoEventsDLQUrl",
        )

        CfnOutput(
            self,
            "AuditDLQUrl",
            value=self.audit_dlq.queue_url,
            description="Dead Letter Queue URL for failed audit events",
            export_name="TangoAuditDLQUrl",
        )

        CfnOutput(
            self,
            "AuditLambdaArn",
            value=self.audit_lambda.function_arn,
            description="Audit consumer Lambda ARN",
            export_name="TangoAuditConsumerArn",
        )

        CfnOutput(
            self,
            "PublisherLambdaArn",
            value=self.publisher_lambda.function_arn,
            description="Event publisher Lambda ARN",
            export_name="TangoEventPublisherArn",
        )
