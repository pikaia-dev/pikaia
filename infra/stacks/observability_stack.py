"""
Observability stack - CloudWatch dashboards and alarms.

Provides operational visibility into:
- API performance (latency, error rates, request volume)
- ECS service health (CPU, memory, task count)
- Database health (connections, CPU, storage)

Alarms notify via SNS topic for:
- High error rates
- Elevated latency
- Unhealthy infrastructure
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_rds as rds,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
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
        ecs_service: ecs.FargateService,
        database: rds.DatabaseCluster,
        alarm_email: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =================================================================
        # SNS Topic for Alarms
        # =================================================================

        self.alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name="tango-alarms",
            display_name="Tango Infrastructure Alarms",
        )

        if alarm_email:
            self.alarm_topic.add_subscription(
                sns_subscriptions.EmailSubscription(alarm_email)
            )

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

        # Database metrics
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

        # =================================================================
        # Alarms
        # =================================================================

        # High 5xx error rate (>5% of requests)
        error_rate_alarm = cloudwatch.Alarm(
            self,
            "HighErrorRateAlarm",
            alarm_name="tango-high-error-rate",
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
            alarm_name="tango-high-latency",
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
            alarm_name="tango-unhealthy-hosts",
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
            alarm_name="tango-ecs-high-cpu",
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
            alarm_name="tango-ecs-high-memory",
            alarm_description="ECS service memory utilization exceeds 85%",
            metric=ecs_memory,
            threshold=85,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        ecs_memory_alarm.add_alarm_action(alarm_action)
        ecs_memory_alarm.add_ok_action(alarm_action)

        # High database CPU (>80%)
        db_cpu_alarm = cloudwatch.Alarm(
            self,
            "DbHighCpuAlarm",
            alarm_name="tango-db-high-cpu",
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
            alarm_name="tango-db-high-connections",
            alarm_description="Database connections exceeding threshold (>500)",
            metric=db_connections,
            threshold=500,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        db_connections_alarm.add_alarm_action(alarm_action)
        db_connections_alarm.add_ok_action(alarm_action)

        # =================================================================
        # Dashboard
        # =================================================================

        dashboard = cloudwatch.Dashboard(
            self,
            "TangoDashboard",
            dashboard_name="tango-operations",
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

        # Row 3: Database
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

        # Row 4: Alarm Status
        dashboard.add_widgets(
            cloudwatch.AlarmStatusWidget(
                title="Alarm Status",
                alarms=[
                    error_rate_alarm,
                    latency_alarm,
                    unhealthy_alarm,
                    ecs_cpu_alarm,
                    ecs_memory_alarm,
                    db_cpu_alarm,
                    db_connections_alarm,
                ],
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
            value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name=tango-operations",
            description="CloudWatch Dashboard URL",
        )

        CfnOutput(
            self,
            "AlarmTopicArn",
            value=self.alarm_topic.topic_arn,
            description="SNS Topic ARN for alarm notifications",
            export_name="TangoAlarmTopicArn",
        )
