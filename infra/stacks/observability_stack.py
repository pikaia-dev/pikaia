"""
Observability stack - CloudWatch dashboards and alarms.

Provides operational visibility into:
- API performance (latency, error rates, request volume)
- ECS service health (CPU, memory, task count)
- Database health (connections, CPU, storage)
- Lambda health (errors, duration, throttling)
- EventBridge delivery (failed invocations)

Alarms notify via SNS topic for:
- High error rates
- Elevated latency
- Unhealthy infrastructure
- Lambda failures
- Event delivery failures
- Dead letter queue messages (failed events requiring investigation)
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
)
from aws_cdk import (
    aws_cloudwatch_actions as cw_actions,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import (
    aws_events as events,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_rds as rds,
)
from aws_cdk import (
    aws_sns as sns,
)
from aws_cdk import (
    aws_sns_subscriptions as sns_subscriptions,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from constructs import Construct


class ObservabilityStack(Stack):
    """
    CloudWatch dashboards and alarms for operational monitoring.

    Creates:
    - Main operational dashboard with API, ECS, and database metrics
    - Critical alarms with SNS notifications
    - Log Insights query templates (documented in observability.md)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        alb: elbv2.IApplicationLoadBalancer,
        target_group: elbv2.IApplicationTargetGroup,
        ecs_cluster: ecs.ICluster,
        ecs_service: ecs.FargateService | ecs.IService,
        database: rds.DatabaseCluster | None = None,
        event_bus: events.IEventBus | None = None,
        publisher_lambda: lambda_.IFunction | None = None,
        audit_lambda: lambda_.IFunction | None = None,
        publisher_dlq: sqs.IQueue | None = None,
        audit_dlq: sqs.IQueue | None = None,
        alarm_email: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Resource naming from CDK context (allows customization without code changes)
        resource_prefix = self.node.try_get_context("resource_prefix") or "pikaia"
        alarm_topic_name = (
            self.node.try_get_context("alarm_topic_name") or f"{resource_prefix}-alarms"
        )
        dashboard_name = (
            self.node.try_get_context("dashboard_name") or f"{resource_prefix}-operations"
        )

        # =================================================================
        # SNS Topic for Alarms
        # =================================================================

        self.alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=alarm_topic_name,
            display_name=f"{resource_prefix.title()} Infrastructure Alarms",
        )

        if alarm_email:
            self.alarm_topic.add_subscription(sns_subscriptions.EmailSubscription(alarm_email))

        alarm_action = cw_actions.SnsAction(self.alarm_topic)

        # =================================================================
        # Metrics
        # =================================================================

        # ALB metrics
        alb_request_count = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="RequestCount",
            dimensions_map={
                "LoadBalancer": alb.load_balancer_full_name,
            },
            statistic="Sum",
            period=Duration.minutes(1),
        )

        alb_5xx_count = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="HTTPCode_ELB_5XX_Count",
            dimensions_map={
                "LoadBalancer": alb.load_balancer_full_name,
            },
            statistic="Sum",
            period=Duration.minutes(1),
        )

        alb_target_5xx_count = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="HTTPCode_Target_5XX_Count",
            dimensions_map={
                "LoadBalancer": alb.load_balancer_full_name,
            },
            statistic="Sum",
            period=Duration.minutes(1),
        )

        target_response_time = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="TargetResponseTime",
            dimensions_map={
                "LoadBalancer": alb.load_balancer_full_name,
            },
            statistic="p99",
            period=Duration.minutes(1),
        )

        target_response_time_p50 = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="TargetResponseTime",
            dimensions_map={
                "LoadBalancer": alb.load_balancer_full_name,
            },
            statistic="p50",
            period=Duration.minutes(1),
        )

        healthy_host_count = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="HealthyHostCount",
            dimensions_map={
                "LoadBalancer": alb.load_balancer_full_name,
                "TargetGroup": target_group.target_group_full_name,
            },
            statistic="Minimum",
            period=Duration.minutes(1),
        )

        # ECS metrics
        ecs_cpu = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="CPUUtilization",
            dimensions_map={
                "ClusterName": ecs_cluster.cluster_name,
                "ServiceName": ecs_service.service_name,
            },
            statistic="Average",
            period=Duration.minutes(1),
        )

        ecs_memory = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="MemoryUtilization",
            dimensions_map={
                "ClusterName": ecs_cluster.cluster_name,
                "ServiceName": ecs_service.service_name,
            },
            statistic="Average",
            period=Duration.minutes(1),
        )

        # Database metrics (optional - only if database is provided)
        db_connections = None
        db_cpu = None
        db_serverless_capacity = None
        db_read_latency = None
        db_write_latency = None

        if database:
            db_connections = cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="DatabaseConnections",
                dimensions_map={
                    "DBClusterIdentifier": database.cluster_identifier,
                },
                statistic="Average",
                period=Duration.minutes(1),
            )

            db_cpu = cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="CPUUtilization",
                dimensions_map={
                    "DBClusterIdentifier": database.cluster_identifier,
                },
                statistic="Average",
                period=Duration.minutes(1),
            )

            db_serverless_capacity = cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="ServerlessDatabaseCapacity",
                dimensions_map={
                    "DBClusterIdentifier": database.cluster_identifier,
                },
                statistic="Average",
                period=Duration.minutes(1),
            )

            db_read_latency = cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="ReadLatency",
                dimensions_map={
                    "DBClusterIdentifier": database.cluster_identifier,
                },
                statistic="Average",
                period=Duration.minutes(1),
            )

            db_write_latency = cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="WriteLatency",
                dimensions_map={
                    "DBClusterIdentifier": database.cluster_identifier,
                },
                statistic="Average",
                period=Duration.minutes(1),
            )

        # Lambda metrics (optional - only if event stack is deployed)
        lambda_metrics: dict[str, dict[str, cloudwatch.Metric]] = {}
        if publisher_lambda:
            lambda_metrics["publisher"] = self._create_lambda_metrics(
                publisher_lambda, "EventPublisher"
            )
        if audit_lambda:
            lambda_metrics["audit"] = self._create_lambda_metrics(audit_lambda, "AuditConsumer")

        # EventBridge metrics (optional)
        eventbridge_failed_invocations = None
        if event_bus:
            eventbridge_failed_invocations = cloudwatch.Metric(
                namespace="AWS/Events",
                metric_name="FailedInvocations",
                dimensions_map={
                    "EventBusName": event_bus.event_bus_name,
                },
                statistic="Sum",
                period=Duration.minutes(5),
            )

        # =================================================================
        # Alarms
        # =================================================================

        # High 5xx error rate (>5% of requests)
        error_rate_alarm = cloudwatch.Alarm(
            self,
            "HighErrorRateAlarm",
            alarm_name=f"{resource_prefix}-high-error-rate",
            alarm_description="API 5xx error rate exceeds 5% of requests",
            metric=cloudwatch.MathExpression(
                expression="(elb5xx + target5xx) / requests * 100",
                using_metrics={
                    "elb5xx": alb_5xx_count,
                    "target5xx": alb_target_5xx_count,
                    "requests": alb_request_count,
                },
                period=Duration.minutes(5),
            ),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        error_rate_alarm.add_alarm_action(alarm_action)
        error_rate_alarm.add_ok_action(alarm_action)

        # High latency (p99 > 2 seconds)
        latency_alarm = cloudwatch.Alarm(
            self,
            "HighLatencyAlarm",
            alarm_name=f"{resource_prefix}-high-latency",
            alarm_description="API p99 latency exceeds 2 seconds",
            metric=target_response_time,
            threshold=2,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        latency_alarm.add_alarm_action(alarm_action)
        latency_alarm.add_ok_action(alarm_action)

        # No healthy hosts
        unhealthy_alarm = cloudwatch.Alarm(
            self,
            "UnhealthyHostsAlarm",
            alarm_name=f"{resource_prefix}-unhealthy-hosts",
            alarm_description="No healthy ECS tasks behind load balancer",
            metric=healthy_host_count,
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )
        unhealthy_alarm.add_alarm_action(alarm_action)
        unhealthy_alarm.add_ok_action(alarm_action)

        # High ECS CPU (>85%)
        ecs_cpu_alarm = cloudwatch.Alarm(
            self,
            "EcsHighCpuAlarm",
            alarm_name=f"{resource_prefix}-ecs-high-cpu",
            alarm_description="ECS service CPU utilization exceeds 85%",
            metric=ecs_cpu,
            threshold=85,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        ecs_cpu_alarm.add_alarm_action(alarm_action)
        ecs_cpu_alarm.add_ok_action(alarm_action)

        # High ECS memory (>85%)
        ecs_memory_alarm = cloudwatch.Alarm(
            self,
            "EcsHighMemoryAlarm",
            alarm_name=f"{resource_prefix}-ecs-high-memory",
            alarm_description="ECS service memory utilization exceeds 85%",
            metric=ecs_memory,
            threshold=85,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        ecs_memory_alarm.add_alarm_action(alarm_action)
        ecs_memory_alarm.add_ok_action(alarm_action)

        # Database alarms (optional - only if database is provided)
        db_cpu_alarm = None
        db_connections_alarm = None

        if database and db_cpu and db_connections:
            # High database CPU (>80%)
            db_cpu_alarm = cloudwatch.Alarm(
                self,
                "DbHighCpuAlarm",
                alarm_name=f"{resource_prefix}-db-high-cpu",
                alarm_description="Aurora database CPU exceeds 80%",
                metric=db_cpu,
                threshold=80,
                evaluation_periods=3,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            db_cpu_alarm.add_alarm_action(alarm_action)
            db_cpu_alarm.add_ok_action(alarm_action)

            # High database connections (approaching limit)
            # Aurora Serverless v2 has ~2000 connections per ACU
            db_connections_alarm = cloudwatch.Alarm(
                self,
                "DbHighConnectionsAlarm",
                alarm_name=f"{resource_prefix}-db-high-connections",
                alarm_description="Database connections exceeding threshold (>500)",
                metric=db_connections,
                threshold=500,
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            db_connections_alarm.add_alarm_action(alarm_action)
            db_connections_alarm.add_ok_action(alarm_action)

        # Lambda alarms (optional)
        lambda_alarms: list[cloudwatch.Alarm] = []

        if publisher_lambda and "publisher" in lambda_metrics:
            publisher_error_alarm = cloudwatch.Alarm(
                self,
                "PublisherLambdaErrorAlarm",
                alarm_name=f"{resource_prefix}-event-publisher-errors",
                alarm_description="Event publisher Lambda has errors",
                metric=lambda_metrics["publisher"]["errors"],
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            publisher_error_alarm.add_alarm_action(alarm_action)
            publisher_error_alarm.add_ok_action(alarm_action)
            lambda_alarms.append(publisher_error_alarm)

            publisher_throttle_alarm = cloudwatch.Alarm(
                self,
                "PublisherLambdaThrottleAlarm",
                alarm_name=f"{resource_prefix}-event-publisher-throttles",
                alarm_description="Event publisher Lambda is being throttled",
                metric=lambda_metrics["publisher"]["throttles"],
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            publisher_throttle_alarm.add_alarm_action(alarm_action)
            publisher_throttle_alarm.add_ok_action(alarm_action)
            lambda_alarms.append(publisher_throttle_alarm)

        if audit_lambda and "audit" in lambda_metrics:
            audit_error_alarm = cloudwatch.Alarm(
                self,
                "AuditLambdaErrorAlarm",
                alarm_name=f"{resource_prefix}-audit-consumer-errors",
                alarm_description="Audit consumer Lambda has errors",
                metric=lambda_metrics["audit"]["errors"],
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            audit_error_alarm.add_alarm_action(alarm_action)
            audit_error_alarm.add_ok_action(alarm_action)
            lambda_alarms.append(audit_error_alarm)

        # EventBridge delivery failures alarm
        eventbridge_alarm = None
        if eventbridge_failed_invocations:
            eventbridge_alarm = cloudwatch.Alarm(
                self,
                "EventBridgeFailedInvocationsAlarm",
                alarm_name=f"{resource_prefix}-eventbridge-failed-invocations",
                alarm_description="EventBridge rule invocations are failing",
                metric=eventbridge_failed_invocations,
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            eventbridge_alarm.add_alarm_action(alarm_action)
            eventbridge_alarm.add_ok_action(alarm_action)

        # SQS Dead Letter Queue alarms
        dlq_alarms: list[cloudwatch.Alarm] = []

        if publisher_dlq:
            publisher_dlq_alarm = cloudwatch.Alarm(
                self,
                "PublisherDlqAlarm",
                alarm_name=f"{resource_prefix}-publisher-dlq-messages",
                alarm_description=(
                    "Event publisher DLQ has messages — failed events require investigation"
                ),
                metric=publisher_dlq.metric_approximate_number_of_messages_visible(
                    period=Duration.minutes(1),
                    statistic="Maximum",
                ),
                threshold=0,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            publisher_dlq_alarm.add_alarm_action(alarm_action)
            publisher_dlq_alarm.add_ok_action(alarm_action)
            dlq_alarms.append(publisher_dlq_alarm)

        if audit_dlq:
            audit_dlq_alarm = cloudwatch.Alarm(
                self,
                "AuditDlqAlarm",
                alarm_name=f"{resource_prefix}-audit-dlq-messages",
                alarm_description=(
                    "Audit consumer DLQ has messages — failed audit events require investigation"
                ),
                metric=audit_dlq.metric_approximate_number_of_messages_visible(
                    period=Duration.minutes(1),
                    statistic="Maximum",
                ),
                threshold=0,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            audit_dlq_alarm.add_alarm_action(alarm_action)
            audit_dlq_alarm.add_ok_action(alarm_action)
            dlq_alarms.append(audit_dlq_alarm)

        # =================================================================
        # Dashboard
        # =================================================================

        dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=dashboard_name,
        )

        # Row 1: API Overview
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Request Rate",
                left=[alb_request_count],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="API Error Rate (5xx)",
                left=[alb_5xx_count, alb_target_5xx_count],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="API Latency",
                left=[target_response_time_p50, target_response_time],
                left_y_axis=cloudwatch.YAxisProps(
                    label="Seconds",
                    min=0,
                ),
                width=8,
                height=6,
            ),
        )

        # Row 2: ECS Service
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ECS CPU Utilization",
                left=[ecs_cpu],
                left_y_axis=cloudwatch.YAxisProps(
                    label="Percent",
                    min=0,
                    max=100,
                ),
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="ECS Memory Utilization",
                left=[ecs_memory],
                left_y_axis=cloudwatch.YAxisProps(
                    label="Percent",
                    min=0,
                    max=100,
                ),
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Healthy Host Count",
                left=[healthy_host_count],
                left_y_axis=cloudwatch.YAxisProps(
                    label="Hosts",
                    min=0,
                ),
                width=8,
                height=6,
            ),
        )

        # Row 3: Database (if database is provided)
        if database and db_connections and db_cpu and db_serverless_capacity:
            dashboard.add_widgets(
                cloudwatch.GraphWidget(
                    title="Database Connections",
                    left=[db_connections],
                    width=6,
                    height=6,
                ),
                cloudwatch.GraphWidget(
                    title="Database CPU",
                    left=[db_cpu],
                    left_y_axis=cloudwatch.YAxisProps(
                        label="Percent",
                        min=0,
                        max=100,
                    ),
                    width=6,
                    height=6,
                ),
                cloudwatch.GraphWidget(
                    title="Aurora Serverless Capacity (ACU)",
                    left=[db_serverless_capacity],
                    width=6,
                    height=6,
                ),
                cloudwatch.GraphWidget(
                    title="Database Latency",
                    left=[db_read_latency, db_write_latency],
                    left_y_axis=cloudwatch.YAxisProps(
                        label="Seconds",
                        min=0,
                    ),
                    width=6,
                    height=6,
                ),
            )

        # Row 4: Lambda & Events (if configured)
        if lambda_metrics or eventbridge_failed_invocations:
            lambda_widgets = []

            if "publisher" in lambda_metrics:
                lambda_widgets.append(
                    cloudwatch.GraphWidget(
                        title="Event Publisher Lambda",
                        left=[
                            lambda_metrics["publisher"]["invocations"],
                            lambda_metrics["publisher"]["errors"],
                        ],
                        right=[lambda_metrics["publisher"]["duration"]],
                        width=8,
                        height=6,
                    )
                )

            if "audit" in lambda_metrics:
                lambda_widgets.append(
                    cloudwatch.GraphWidget(
                        title="Audit Consumer Lambda",
                        left=[
                            lambda_metrics["audit"]["invocations"],
                            lambda_metrics["audit"]["errors"],
                        ],
                        right=[lambda_metrics["audit"]["duration"]],
                        width=8,
                        height=6,
                    )
                )

            if eventbridge_failed_invocations:
                lambda_widgets.append(
                    cloudwatch.GraphWidget(
                        title="EventBridge Delivery",
                        left=[eventbridge_failed_invocations],
                        width=8,
                        height=6,
                    )
                )

            if lambda_widgets:
                dashboard.add_widgets(*lambda_widgets)

        # Row 5: Alarm Status
        all_alarms = [
            error_rate_alarm,
            latency_alarm,
            unhealthy_alarm,
            ecs_cpu_alarm,
            ecs_memory_alarm,
        ]
        # Add database alarms if available
        if db_cpu_alarm:
            all_alarms.append(db_cpu_alarm)
        if db_connections_alarm:
            all_alarms.append(db_connections_alarm)
        all_alarms.extend(lambda_alarms)
        if eventbridge_alarm:
            all_alarms.append(eventbridge_alarm)
        all_alarms.extend(dlq_alarms)

        dashboard.add_widgets(
            cloudwatch.AlarmStatusWidget(
                title="Alarm Status",
                alarms=all_alarms,
                width=24,
                height=4,
            ),
        )

        # =================================================================
        # Outputs
        # =================================================================

        CfnOutput(
            self,
            "DashboardUrl",
            value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard_name}",
            description="CloudWatch Dashboard URL",
        )

        CfnOutput(
            self,
            "AlarmTopicArn",
            value=self.alarm_topic.topic_arn,
            description="SNS Topic ARN for alarm notifications",
            export_name=f"{resource_prefix.title()}AlarmTopicArn",
        )

    def _create_lambda_metrics(
        self, fn: lambda_.IFunction, name_prefix: str
    ) -> dict[str, cloudwatch.Metric]:
        """Create standard metrics for a Lambda function."""
        return {
            "errors": cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name="Errors",
                dimensions_map={"FunctionName": fn.function_name},
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            "duration": cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name="Duration",
                dimensions_map={"FunctionName": fn.function_name},
                statistic="p99",
                period=Duration.minutes(5),
            ),
            "throttles": cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name="Throttles",
                dimensions_map={"FunctionName": fn.function_name},
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            "invocations": cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions_map={"FunctionName": fn.function_name},
                statistic="Sum",
                period=Duration.minutes(5),
            ),
        }
