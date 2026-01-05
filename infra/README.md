# Infrastructure (AWS CDK)




AWS CDK stacks for deploying Tango to AWS.




## Prerequisites




- Python 3.12+ (3.12 recommended for CDK compatibility)
- Node.js 20+ (for CDK CLI and Lambda@Edge)
- AWS CLI configured with credentials
- Docker (for Lambda bundling with native dependencies)




## Setup




```bash
cd infra
uv sync




# Install Node.js dependencies for Lambda functions
cd functions/image-transform && npm install && cd ../..
```




## Stacks




| Stack | Description |
|-------|-------------|
| **TangoNetwork** | VPC with public/private subnets, NAT gateway |
| **TangoApp** | Aurora PostgreSQL Serverless v2, ECS Fargate, ALB, Secrets |
| **TangoMedia** | S3 bucket, CloudFront CDN, image transformation Lambda@Edge |
| **TangoEvents** | EventBridge bus, publisher Lambda, SQS DLQ |




## Deployment




### First-time Setup




```bash
# Bootstrap CDK (once per account/region)
npx cdk bootstrap aws://ACCOUNT_ID/REGION




# Deploy foundation stacks
npx cdk deploy TangoNetwork TangoApp
```




### Full Deployment




```bash
# Deploy all stacks
npx cdk deploy --all




# With custom domain and certificate
npx cdk deploy TangoApp \
  --context domain_name=api.example.com \
  --context certificate_arn=arn:aws:acm:us-east-1:123456789:certificate/xxx
<!-- Trigger CDK deploy 2 -->
