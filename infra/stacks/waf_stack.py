"""
WAF stack - AWS WAF WebACLs for ALB and CloudFront protection.

This stack creates two WebACLs:
- Regional WebACL (REGIONAL scope) for the Application Load Balancer
- CloudFront WebACL (CLOUDFRONT scope) for CloudFront distributions

Both use AWS Managed Rule Groups:
- AWSManagedRulesCommonRuleSet: Core rule set with broad protection
- AWSManagedRulesKnownBadInputsRuleSet: Blocks known bad inputs (Log4j, etc.)
"""

from aws_cdk import (
    CfnOutput,
    Stack,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from constructs import Construct

# AWS Managed Rule Groups applied to both WebACLs
_MANAGED_RULE_GROUPS = [
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


def _build_managed_rules() -> list[wafv2.CfnWebACL.RuleProperty]:
    """Build WAF rule properties from managed rule group definitions."""
    return [
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
    ]


class WafStack(Stack):
    """
    Creates AWS WAF WebACLs for ALB and CloudFront protection.

    Two WebACLs are created because AWS WAF requires different scopes:
    - REGIONAL scope for ALB (deployed in the stack's region)
    - CLOUDFRONT scope for CloudFront distributions (must be us-east-1)

    In standalone mode, the regional WebACL is associated with the ALB
    directly via CfnWebACLAssociation. In shared mode, the ALB is managed
    externally and WAF should be configured there.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        resource_prefix = self.node.try_get_context("resource_prefix") or "pikaia"
        rules = _build_managed_rules()

        # =================================================================
        # Regional WebACL (for ALB)
        # =================================================================

        self.regional_web_acl = wafv2.CfnWebACL(
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

        # =================================================================
        # CloudFront WebACL (scope must be CLOUDFRONT / us-east-1)
        # =================================================================

        self.cloudfront_web_acl = wafv2.CfnWebACL(
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

        # =================================================================
        # Outputs
        # =================================================================

        CfnOutput(
            self,
            "RegionalWebAclArn",
            value=self.regional_web_acl.attr_arn,
            description="Regional WAF WebACL ARN (for ALB association)",
        )

        CfnOutput(
            self,
            "CloudFrontWebAclArn",
            value=self.cloudfront_web_acl.attr_arn,
            description="CloudFront WAF WebACL ARN (for CloudFront distributions)",
        )
