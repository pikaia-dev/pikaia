"""
WAF stacks - AWS WAF WebACLs for ALB and CloudFront protection.

Two separate stacks because AWS WAF requires different scopes and regions:
- WafRegionalStack: REGIONAL scope WebACL for ALB (deployed in the ALB's region)
- WafCloudFrontStack: CLOUDFRONT scope WebACL (must be deployed in us-east-1)

Features:
- Rate limiting: 2000 requests per 5-minute window per IP (priority 1)
- AWS Managed Rule Groups:
  - AWSManagedRulesAmazonIpReputationList: Blocks IPs with poor reputation
  - AWSManagedRulesCommonRuleSet: Core rule set with broad protection
  - AWSManagedRulesKnownBadInputsRuleSet: Blocks known bad inputs (Log4j, etc.)
- WAF logging: Request logs sent to CloudWatch Logs for monitoring and analysis
"""

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from constructs import Construct

# AWS Managed Rule Groups applied to both WebACLs
_MANAGED_RULE_GROUPS = [
    {
        "name": "AWSManagedRulesAmazonIpReputationList",
        "vendor": "AWS",
        "priority": 5,
    },
    {
        "name": "AWSManagedRulesCommonRuleSet",
        "vendor": "AWS",
        "priority": 10,
    },
    {
        "name": "AWSManagedRulesKnownBadInputsRuleSet",
        "vendor": "AWS",
        "priority": 20,
    },
]


def _build_rate_limit_rule(
    resource_prefix: str,
) -> wafv2.CfnWebACL.RuleProperty:
    """Build a rate-based rule that limits requests per IP."""
    return wafv2.CfnWebACL.RuleProperty(
        name=f"{resource_prefix}-rate-limit",
        priority=1,
        action=wafv2.CfnWebACL.RuleActionProperty(block={}),
        statement=wafv2.CfnWebACL.StatementProperty(
            rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                limit=2000,
                aggregate_key_type="IP",
            ),
        ),
        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
            cloud_watch_metrics_enabled=True,
            metric_name=f"{resource_prefix}-rate-limit",
            sampled_requests_enabled=True,
        ),
    )


def _build_managed_rules(
    resource_prefix: str,
) -> list[wafv2.CfnWebACL.RuleProperty]:
    """Build WAF rule properties including rate limiting and managed rule groups."""
    rules: list[wafv2.CfnWebACL.RuleProperty] = [
        _build_rate_limit_rule(resource_prefix),
    ]

    rules.extend(
        wafv2.CfnWebACL.RuleProperty(
            name=rule["name"],
            priority=rule["priority"],
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name=rule["vendor"],
                    name=rule["name"],
                ),
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=rule["name"],
                sampled_requests_enabled=True,
            ),
        )
        for rule in _MANAGED_RULE_GROUPS
    )

    return rules


class WafRegionalStack(Stack):
    """
    Creates a REGIONAL scope AWS WAF WebACL for ALB protection.

    Includes rate limiting (2000 req/5min per IP), IP reputation filtering,
    managed rule groups, and CloudWatch Logs logging.

    Deploy in the same region as the ALB. In standalone mode, the WebACL
    is associated with the ALB via CfnWebACLAssociation in AppStack.
    In shared mode, the ALB is managed externally and WAF should be
    configured there.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        resource_prefix = self.node.try_get_context("resource_prefix") or "pikaia"
        rules = _build_managed_rules(resource_prefix)

        self.web_acl = wafv2.CfnWebACL(
            self,
            "RegionalWebAcl",
            name=f"{resource_prefix}-regional-waf",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            rules=rules,
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=f"{resource_prefix}-regional-waf",
                sampled_requests_enabled=True,
            ),
        )

        waf_log_group = logs.LogGroup(
            self,
            "RegionalWafLogGroup",
            log_group_name=f"aws-waf-logs-{resource_prefix}-regional",
            retention=logs.RetentionDays.NINETY_DAYS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        wafv2.CfnLoggingConfiguration(
            self,
            "RegionalWafLogging",
            resource_arn=self.web_acl.attr_arn,
            log_destination_configs=[waf_log_group.log_group_arn],
        )

        CfnOutput(
            self,
            "WebAclArn",
            value=self.web_acl.attr_arn,
            description="Regional WAF WebACL ARN (for ALB association)",
        )


class WafCloudFrontStack(Stack):
    """
    Creates a CLOUDFRONT scope AWS WAF WebACL for CloudFront distributions.

    Includes rate limiting (2000 req/5min per IP), IP reputation filtering,
    managed rule groups, and CloudWatch Logs logging.

    This stack MUST be deployed in us-east-1 because AWS WAF requires
    CLOUDFRONT scope WebACLs to be in us-east-1, regardless of where
    the application stacks are deployed.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        resource_prefix = self.node.try_get_context("resource_prefix") or "pikaia"
        rules = _build_managed_rules(resource_prefix)

        self.web_acl = wafv2.CfnWebACL(
            self,
            "CloudFrontWebAcl",
            name=f"{resource_prefix}-cloudfront-waf",
            scope="CLOUDFRONT",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            rules=rules,
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=f"{resource_prefix}-cloudfront-waf",
                sampled_requests_enabled=True,
            ),
        )

        waf_log_group = logs.LogGroup(
            self,
            "CloudFrontWafLogGroup",
            log_group_name=f"aws-waf-logs-{resource_prefix}-cloudfront",
            retention=logs.RetentionDays.NINETY_DAYS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        wafv2.CfnLoggingConfiguration(
            self,
            "CloudFrontWafLogging",
            resource_arn=self.web_acl.attr_arn,
            log_destination_configs=[waf_log_group.log_group_arn],
        )

        CfnOutput(
            self,
            "WebAclArn",
            value=self.web_acl.attr_arn,
            description="CloudFront WAF WebACL ARN (for CloudFront distributions)",
        )
