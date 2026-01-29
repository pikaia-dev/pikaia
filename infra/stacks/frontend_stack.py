"""
Frontend stack - S3 + CloudFront for React/Vite SPA.

This stack deploys the frontend with:
- S3 bucket for static files (private, CloudFront access only)
- CloudFront distribution with:
  - S3 origin for frontend assets
  - ALB origin for /api/* routes
  - SPA routing (404 → index.html)
  - Optional custom domain with ACM certificate
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_certificatemanager as acm,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct


class FrontendStack(Stack):
    """
    Creates S3 + CloudFront infrastructure for the frontend SPA.

    Features:
    - S3 bucket with private access (no public website hosting)
    - CloudFront distribution with Origin Access Control
    - API routing to ALB for /api/* paths
    - SPA routing (all 404s redirect to index.html)
    - Optional custom domain with SSL certificate
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        alb: elbv2.IApplicationLoadBalancer,
        domain_name: str | None = None,
        certificate_arn: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Resource naming from CDK context (allows customization without code changes)
        frontend_bucket_prefix = self.node.try_get_context("frontend_bucket_prefix") or "pikaia-frontend"
        resource_prefix = self.node.try_get_context("resource_prefix") or "pikaia"

        # S3 bucket for frontend static files
        self.frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"{frontend_bucket_prefix}-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # Origin Access Control for CloudFront → S3
        oac = cloudfront.S3OriginAccessControl(
            self,
            "FrontendOAC",
            signing=cloudfront.Signing.SIGV4_ALWAYS,
        )

        # S3 origin with OAC
        s3_origin = origins.S3BucketOrigin.with_origin_access_control(
            self.frontend_bucket,
            origin_access_control=oac,
        )

        # ALB origin for API routes
        # Use HTTP to ALB, but add custom headers so Django knows original was HTTPS
        alb_origin = origins.HttpOrigin(
            alb.load_balancer_dns_name,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            http_port=80,
            custom_headers={
                "CloudFront-Forwarded-Proto": "https",
            },
        )

        # Certificate for custom domain
        certificate = None
        domain_names = None
        if certificate_arn and domain_name:
            certificate = acm.Certificate.from_certificate_arn(self, "Certificate", certificate_arn)
            domain_names = [domain_name]

        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self,
            "FrontendDistribution",
            comment=f"{resource_prefix.title()} SaaS Frontend",
            domain_names=domain_names,
            certificate=certificate,
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=alb_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                ),
            },
            default_root_object="index.html",
            # SPA routing - redirect 404s to index.html
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # North America + Europe
        )

        # Outputs
        CfnOutput(
            self,
            "FrontendBucketName",
            value=self.frontend_bucket.bucket_name,
            description="S3 bucket name for frontend static files",
        )

        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID for cache invalidation",
        )

        CfnOutput(
            self,
            "CloudFrontDomainName",
            value=self.distribution.distribution_domain_name,
            description="CloudFront domain name",
        )

        if domain_name:
            CfnOutput(
                self,
                "FrontendURL",
                value=f"https://{domain_name}",
                description="Frontend URL (custom domain)",
            )
        else:
            CfnOutput(
                self,
                "FrontendURL",
                value=f"https://{self.distribution.distribution_domain_name}",
                description="Frontend URL",
            )
