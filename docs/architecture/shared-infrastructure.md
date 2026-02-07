# Shared Infrastructure Mode

Pikaia supports running in **shared infrastructure mode**, allowing multiple projects to share expensive AWS resources (VPC, NAT Gateway, ALB, Aurora database) while maintaining isolation at the application level.

## Overview

### Cost Comparison

| Scenario | Monthly Cost |
|----------|-------------|
| 1 project standalone | ~$120 |
| 1 project shared (base infrastructure) | ~$90 |
| 2 projects sharing infrastructure | ~$105 (~$52/each) |
| 3 projects sharing infrastructure | ~$120 (~$40/each) |

### Architecture

```
Provider deployment (standalone + export)
├── NetworkStack → VPC, NAT Gateway, subnets
├── AppStack → Aurora cluster, RDS Proxy, ALB, HTTPS listener, ECS
└── SharedExportStack → writes 11 SSM Parameters
    ↓ SSM Parameters
Consumer deployment (shared mode)
├── Detects shared_infra_prefix context flag
├── Reads VPC/ALB/database from SSM
└── Creates only: ECS service, target group, listener rule
```

## Shared Resources via SSM Parameters

The following SSM parameters are used to share infrastructure between deployments:

```
{prefix}/network/vpc-id
{prefix}/network/private-subnet-ids
{prefix}/network/public-subnet-ids
{prefix}/network/availability-zones

{prefix}/alb/arn
{prefix}/alb/dns-name
{prefix}/alb/security-group-id
{prefix}/alb/https-listener-arn

{prefix}/database/cluster-endpoint
{prefix}/database/security-group-id
{prefix}/database/proxy-endpoint
```

## Setting Up Shared Infrastructure

There are two ways to provide shared infrastructure:

### Option A: Export from Standalone (Recommended)

The simplest approach — deploy one project in standalone mode and export its resources via SSM parameters. No separate repo required.

**Prerequisites:**
- A standalone deployment with HTTPS configured (`certificate_arn` required)
- The provider's database is created automatically by CDK

**Deploy the provider:**

```bash
cd infra && npx cdk deploy --all \
  --context export_shared_infra_prefix=/shared-infra/prod \
  --context certificate_arn=arn:aws:acm:us-east-1:ACCOUNT:certificate/ID \
  --context domain_name=api.provider.com
```

This deploys the full standalone stack plus a `PikaiaSharedExport` stack that writes 11 SSM parameters. Consumer deployments can then read these parameters.

### Option B: Dedicated Shared-Infra Repo

For centralized management, create a private repo with CDK stacks that export to SSM. This separates infrastructure ownership from application code.

```python
# Example: shared_network_stack.py
class SharedNetworkStack(Stack):
    def __init__(self, scope, construct_id, *, env_name: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(self, "SharedVpc", max_azs=2, nat_gateways=1)

        ssm.StringParameter(self, "VpcIdParam",
            parameter_name=f"/shared-infra/{env_name}/network/vpc-id",
            string_value=self.vpc.vpc_id,
        )
        # ... more parameters for all 11 values
```

## Adding a Consumer Project

### 1. Create Project Database

Each consumer needs its own database within the shared Aurora cluster. Use the provided script:

```bash
./scripts/create-project-database.sh myproject <cluster-endpoint> [aws-profile]
```

This creates:
- PostgreSQL database: `myproject`
- PostgreSQL user: `myproject_user`
- Secrets Manager secret: `myproject/database-credentials`

You'll need network access to the Aurora cluster (e.g., via VPN or bastion) and the master password from the provider's Secrets Manager.

### 2. Bootstrap Application Secrets

```bash
RESOURCE_PREFIX=myproject ./scripts/bootstrap-infra.sh your-profile
RESOURCE_PREFIX=myproject ./scripts/bootstrap-secrets.sh your-profile
```

### 3. Deploy in Shared Mode

```bash
cd infra && npx cdk deploy --all \
  --context shared_infra_prefix=/shared-infra/prod \
  --context domain_name=api.myproject.com \
  --context alb_rule_priority=200 \
  --context resource_prefix=myproject
```

### 4. Assign ALB Rule Priority

Each project needs a unique ALB listener rule priority. Track assignments:

| Project | Priority | Domain |
|---------|----------|--------|
| provider (pikaia) | — (default listener) | api.pikaia.dev |
| consumer-a | 100 | api.consumer-a.com |
| consumer-b | 200 | api.consumer-b.com |

## Usage

### Standalone Mode (Default)

```bash
# Creates all resources: VPC, ALB, Aurora, ECS
cdk deploy --all
```

### Shared Mode

```bash
# Uses shared VPC, ALB, database from SSM parameters
cdk deploy --all \
  --context shared_infra_prefix=/shared-infra/prod \
  --context domain_name=api.yourproject.com \
  --context alb_rule_priority=100
```

### Required Context for Shared Mode

| Parameter | Description | Example |
|-----------|-------------|---------|
| `shared_infra_prefix` | SSM parameter prefix | `/shared-infra/prod` |
| `domain_name` | API domain for host-based routing | `api.yourproject.com` |
| `alb_rule_priority` | Unique priority (100-999) | `100` |

### Export Context (Provider Only)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `export_shared_infra_prefix` | SSM prefix to write parameters to | `/shared-infra/prod` |
| `certificate_arn` | Required — HTTPS needed for listener rules | `arn:aws:acm:...` |

### Optional Context

| Parameter | Description | Default |
|-----------|-------------|---------|
| `database_secret_path` | Project-specific DB credentials | `{resource_prefix}/database-credentials` |
| `resource_prefix` | Prefix for all resources | `pikaia` |

## Mutual Exclusivity

A deployment cannot be both a provider and a consumer. Setting both `shared_infra_prefix` and `export_shared_infra_prefix` will fail with a validation error.

## Database Isolation

Projects share the Aurora cluster but have separate:
- Databases (PostgreSQL databases within the cluster)
- Users (with access only to their database)
- Secrets (Secrets Manager secrets with credentials)

### Security Considerations

- **Compute sharing**: Projects share Aurora ACU capacity. Heavy queries in one project can affect others.
- **Mitigation**: Set `statement_timeout` per database, connection limits per user.
- **Single point of failure**: Cluster downtime affects all projects.

### When to Graduate to Standalone

Move a project to its own infrastructure when:
- Revenue justifies the cost (~$90/month additional)
- Traffic/database load affects other projects
- Compliance requires full isolation
- Project needs different region/availability requirements

## How It Works

### InfraResolver

The `InfraResolver` class in `infra/stacks/infra_resolver.py` handles mode detection:

```python
resolver = InfraResolver(app, shared_prefix)

if resolver.is_shared_mode:
    vpc = resolver.lookup_vpc(scope)
    alb = resolver.lookup_alb(scope)
    # ... use shared resources
else:
    # Create resources normally
```

### SharedExportStack

The `SharedExportStack` in `infra/stacks/shared_export_stack.py` writes SSM parameters from standalone resources. It requires all resources as explicit parameters — no optionals, the caller validates.

### Stack Changes

| Stack | Standalone | Shared |
|-------|------------|--------|
| NetworkStack | Creates VPC | Wraps shared VPC |
| AppStack | Creates Aurora, ALB, ECS | Uses shared DB/ALB, creates ECS + target group |
| SharedExportStack | Writes SSM params (if exporting) | Not created |
| FrontendStack | Uses ALB object | Uses ALB DNS string |
| EventsStack | No changes | Uses shared DB security group |
| ObservabilityStack | Full metrics | Skips DB metrics (shared DB) |

## Verification

### Standalone Mode Still Works

```bash
cd infra && cdk synth --all
# Should synthesize all stacks without shared context
```

### Export Mode Synthesizes

```bash
cdk synth --all \
  --context export_shared_infra_prefix=/shared-infra/test \
  --context certificate_arn=arn:aws:acm:us-east-1:123:certificate/test
# PikaiaSharedExport stack appears with 11 SSM parameters
```

### Mutual Exclusivity Fails

```bash
cdk synth --all \
  --context shared_infra_prefix=/x \
  --context export_shared_infra_prefix=/x
# Fails with ValueError
```

### Export Without HTTPS Fails

```bash
cdk synth --all --context export_shared_infra_prefix=/x
# Fails with ValueError (certificate_arn required)
```

### Shared Mode Synthesizes

```bash
cdk synth --all --context shared_infra_prefix=/shared-infra/test
# Should synthesize without VPC/ALB/Aurora resources
# (will fail at deploy if SSM parameters don't exist)
```

## Troubleshooting

### "Parameter not found" during synth

The SSM parameters must exist before running `cdk synth` in shared mode. Deploy the provider (or shared-infra stack) first.

### ALB listener rule priority conflict

Each project must have a unique priority. Check CloudFormation events for conflicts.

### Database connection issues

1. Verify the database secret exists and has correct credentials
2. Check security group allows ECS/Lambda → RDS Proxy
3. Verify RDS Proxy endpoint is correct in SSM
