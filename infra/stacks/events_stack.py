"""
Events stack - EventBridge, Publisher Lambda, and Dead Letter Queue.

This stack implements the event publishing infrastructure:
- Custom EventBridge bus for domain events
- Lambda function to poll outbox and publish events
- Dead Letter Queue for failed event delivery
- CloudWatch scheduled rule for fallback polling
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


class EventsStack(Stack):
    """
    Creates event publishing infrastructure.

    Features:
    - Custom EventBridge bus for domain events
    - Lambda publisher with VPC access for database connectivity
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
        event_bus_name: str = "tango-events",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc
        self.database_secret = database_secret

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
        database_security_group.add_ingress_rule(
            peer=self.lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow event publisher Lambda to connect to RDS",
        )

        # Publisher Lambda function
        self.publisher_lambda = lambda_.Function(
            self,
            "EventPublisher",
            function_name="tango-event-publisher",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(
                str(FUNCTIONS_DIR / "event-publisher"),
                exclude=["tests", "__pycache__", "*.pyc"],
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_12.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -r . /asset-output/",
                    ],
                },
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.lambda_security_group],
            timeout=Duration.seconds(60),
            memory_size=256,
            reserved_concurrent_executions=5,  # Limit concurrency to prevent DB overload
            dead_letter_queue=self.dlq,
            environment={
                "EVENT_BUS_NAME": self.event_bus.event_bus_name,
                "BATCH_SIZE": "100",
                "MAX_ATTEMPTS": "10",
                # DATABASE_URL injected from secret below
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
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
            "PublisherLambdaArn",
            value=self.publisher_lambda.function_arn,
            description="Event publisher Lambda ARN",
            export_name="TangoEventPublisherArn",
        )
