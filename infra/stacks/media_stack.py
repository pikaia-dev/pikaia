"""
Media stack - S3 bucket, CloudFront distribution, and Lambda@Edge for image transformation.

This implements the AWS Dynamic Image Transformation pattern:
https://aws.amazon.com/solutions/implementations/dynamic-image-transformation-for-amazon-cloudfront/
"""

from pathlib import Path

from aws_cdk import (
    BundlingOptions,
    CfnOutput,
    DockerImage,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct

# Path to Lambda functions directory
FUNCTIONS_DIR = Path(__file__).parent.parent / "functions"

# Lambda runtime versions (centralized for easier upgrades)
NODEJS_RUNTIME = lambda_.Runtime.NODEJS_20_X

# Origin Response Lambda configuration (tune based on expected image sizes)
ORIGIN_RESPONSE_MEMORY_MB = 1024  # Sharp needs more memory for image processing
ORIGIN_RESPONSE_TIMEOUT_SECONDS = 30


class MediaStack(Stack):
    """
    Creates S3 bucket with CloudFront distribution and optional image transformation.

    Features:
    - Private S3 bucket for image storage
    - CloudFront distribution for global CDN
    - Lambda@Edge for on-the-fly image resizing using Sharp (Thumbor-compatible URLs)
    - CORS configuration for frontend uploads
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cors_allowed_origins: list[str],
        enable_versioning: bool = False,
        enable_image_transformation: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Resource naming from CDK context
        resource_prefix = self.node.try_get_context("resource_prefix") or "pikaia"

        # S3 bucket for media files (private, accessed via CloudFront)
        self.bucket = s3.Bucket(
            self,
            "MediaBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=enable_versioning,
            removal_policy=RemovalPolicy.RETAIN,
            cors=[
                s3.CorsRule(
                    allowed_headers=[
                        "Content-Type",
                        "Content-Length",
                        "Content-MD5",
                        "x-amz-*",
                    ],
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.POST,
                    ],
                    allowed_origins=cors_allowed_origins,
                    exposed_headers=["ETag"],
                    max_age=3600,
                )
            ],
        )

        # Origin Access Identity for CloudFront -> S3
        origin_access_identity = cloudfront.OriginAccessIdentity(
            self,
            "MediaOAI",
            comment="OAI for media bucket",
        )
        self.bucket.grant_read(origin_access_identity)

        # Configure CloudFront behavior based on image transformation setting
        if enable_image_transformation:
            # Lambda@Edge architecture for image transformation:
            # - ORIGIN_REQUEST: Parses Thumbor-style URLs and rewrites request to S3 key
            # - ORIGIN_RESPONSE: Fetches original from S3, transforms with Sharp, returns result
            origin_request_lambda = self._create_origin_request_lambda()
            origin_response_lambda = self._create_origin_response_lambda()

            default_behavior_config = cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_identity(
                    self.bucket,
                    origin_access_identity=origin_access_identity,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                edge_lambdas=[
                    cloudfront.EdgeLambda(
                        function_version=origin_request_lambda.current_version,
                        event_type=cloudfront.LambdaEdgeEventType.ORIGIN_REQUEST,
                    ),
                    cloudfront.EdgeLambda(
                        function_version=origin_response_lambda.current_version,
                        event_type=cloudfront.LambdaEdgeEventType.ORIGIN_RESPONSE,
                    ),
                ],
            )
        else:
            # Simple passthrough without image transformation
            default_behavior_config = cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_identity(
                    self.bucket,
                    origin_access_identity=origin_access_identity,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
            )

        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self,
            "MediaDistribution",
            default_behavior=default_behavior_config,
            comment=f"{resource_prefix.title()} Media CDN with image transformation",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # US, Canada, Europe
        )

        # Outputs
        CfnOutput(
            self,
            "BucketName",
            value=self.bucket.bucket_name,
            description="S3 bucket name for media storage",
            export_name=f"{resource_prefix.title()}MediaBucketName",
        )

        CfnOutput(
            self,
            "DistributionDomainName",
            value=self.distribution.distribution_domain_name,
            description="CloudFront distribution domain name",
            export_name=f"{resource_prefix.title()}MediaCdnDomain",
        )

        CfnOutput(
            self,
            "ImageTransformUrl",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="Base URL for image transformation (set as IMAGE_TRANSFORM_URL)",
            export_name=f"{resource_prefix.title()}ImageTransformUrl",
        )

    def _create_origin_request_lambda(self) -> lambda_.Function:
        """
        Create Lambda@Edge function for Origin Request (URL rewriting).

        This is a lightweight function that only parses URLs and sets headers.
        No external dependencies needed.
        """
        fn = lambda_.Function(
            self,
            "OriginRequestLambda",
            runtime=NODEJS_RUNTIME,
            handler="index.originRequestHandler",
            code=lambda_.Code.from_asset(
                str(FUNCTIONS_DIR / "image-transform"),
                exclude=["node_modules", "__tests__", "*.test.js"],
            ),
            timeout=Duration.seconds(5),
            memory_size=128,
            description="URL rewriting for image transformation (Origin Request)",
        )

        return fn

    def _create_origin_response_lambda(self) -> lambda_.Function:
        """
        Create Lambda@Edge function for Origin Response (image transformation).

        Uses Sharp library for image processing. Requires Docker bundling
        to compile native binaries for Amazon Linux.
        """
        fn = lambda_.Function(
            self,
            "OriginResponseLambda",
            runtime=NODEJS_RUNTIME,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                str(FUNCTIONS_DIR / "image-transform"),
                bundling=BundlingOptions(
                    image=DockerImage.from_registry("public.ecr.aws/sam/build-nodejs20.x:latest"),
                    command=[
                        "bash",
                        "-c",
                        " && ".join(
                            [
                                "npm ci --omit=dev",
                                "cp -r . /asset-output/",
                                "rm -rf /asset-output/node_modules/.cache",
                                "rm -rf /asset-output/__tests__",
                            ]
                        ),
                    ],
                    user="root",
                ),
            ),
            timeout=Duration.seconds(ORIGIN_RESPONSE_TIMEOUT_SECONDS),
            memory_size=ORIGIN_RESPONSE_MEMORY_MB,
            description="Image transformation using Sharp (Origin Response)",
        )

        # Grant S3 read access for fetching original images
        self.bucket.grant_read(fn)

        return fn
