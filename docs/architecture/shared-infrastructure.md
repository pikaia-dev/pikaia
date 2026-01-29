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
shared-infra repo (private)
├── SharedNetworkStack → VPC, NAT Gateway, subnets
├── SharedAlbStack → ALB, HTTPS listener
└── SharedDatabaseStack → Aurora cluster, RDS Proxy
    ↓ exports to SSM Parameters

pikaia repo (public) + other private repos
├── Detects shared_infra_prefix context flag
├── If set: looks up resources from SSM
└── Creates only: ECS service, target group, listener rule
```

## Shared Resources via SSM Parameters

The shared infrastructure repo exports these SSM parameters:

```
/shared-infra/{env}/network/vpc-id
/shared-infra/{env}/network/private-subnet-ids
/shared-infra/{env}/network/public-subnet-ids
/shared-infra/{env}/network/availability-zones

/shared-infra/{env}/alb/arn
/shared-infra/{env}/alb/dns-name
/shared-infra/{env}/alb/security-group-id
/shared-infra/{env}/alb/https-listener-arn

/shared-infra/{env}/database/cluster-endpoint
/shared-infra/{env}/database/security-group-id
/shared-infra/{env}/database/proxy-endpoint
```

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

### Optional Context

| Parameter | Description | Default |
|-----------|-------------|---------|
| `database_secret_path` | Project-specific DB credentials | `{resource_prefix}/database-credentials` |
| `resource_prefix` | Prefix for all resources | `pikaia` |

## Setting Up Shared Infrastructure

### 1. Create the Shared Infrastructure Repo

Create a private repo with CDK stacks that export to SSM:

```python
# shared_network_stack.py
class SharedNetworkStack(Stack):
    def __init__(self, scope, construct_id, *, env_name: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self, "SharedVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                ),
            ],
        )

        # Export via SSM Parameters
        ssm.StringParameter(self, "VpcIdParam",
            parameter_name=f"/shared-infra/{env_name}/network/vpc-id",
            string_value=self.vpc.vpc_id,
        )
        # ... more parameters
```

### 2. Create Project Database

Each project needs its own database within the shared Aurora cluster:

```bash
#!/bin/bash
# create-project-database.sh

PROJECT_PREFIX=$1
DB_NAME="${PROJECT_PREFIX}"
DB_USER="${PROJECT_PREFIX}_user"
DB_PASSWORD=$(openssl rand -base64 32)

# Connect to Aurora as master user
psql -h $CLUSTER_ENDPOINT -U postgres <<EOF
CREATE DATABASE ${DB_NAME};
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
\c ${DB_NAME}
GRANT ALL ON SCHEMA public TO ${DB_USER};
EOF

# Create project-specific secret
aws secretsmanager create-secret \
    --name "${PROJECT_PREFIX}/database-credentials" \
    --secret-string "{
        \"username\": \"${DB_USER}\",
        \"password\": \"${DB_PASSWORD}\",
        \"host\": \"${CLUSTER_ENDPOINT}\",
        \"port\": \"5432\",
        \"dbname\": \"${DB_NAME}\"
    }"
```

### 3. Assign ALB Rule Priority

Each project needs a unique ALB listener rule priority. Track assignments:

| Project | Priority | Domain |
|---------|----------|--------|
| pikaia-demo | 100 | api.pikaia.dev |
| startup-a | 200 | api.startup-a.com |
| startup-b | 300 | api.startup-b.com |

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

### Stack Changes

| Stack | Standalone | Shared |
|-------|------------|--------|
| NetworkStack | Creates VPC | Wraps shared VPC |
| AppStack | Creates Aurora, ALB, ECS | Uses shared DB/ALB, creates ECS + target group |
| FrontendStack | Uses ALB object | Uses ALB DNS string |
| EventsStack | No changes | Uses shared DB security group |
| ObservabilityStack | Full metrics | Skips DB metrics (shared DB) |

## Verification

### Standalone Mode Still Works

```bash
cd infra && cdk synth --all
# Should synthesize all stacks without shared context
```

### Shared Mode Synthesizes

```bash
cdk synth --all --context shared_infra_prefix=/shared-infra/test
# Should synthesize without VPC/ALB/Aurora resources
# (will fail at deploy if SSM parameters don't exist)
```

## Troubleshooting

### "Parameter not found" during synth

The SSM parameters must exist before running `cdk synth` in shared mode. Deploy the shared-infra stack first.

### ALB listener rule priority conflict

Each project must have a unique priority. Check CloudFormation events for conflicts.

### Database connection issues

1. Verify the database secret exists and has correct credentials
2. Check security group allows Lambda → RDS Proxy
3. Verify RDS Proxy endpoint is correct in SSM
