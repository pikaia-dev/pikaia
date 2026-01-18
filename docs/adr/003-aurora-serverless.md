# ADR 003: Aurora Serverless v2 for Database

**Date:** January 18, 2026

## Context

We need a production PostgreSQL database that:
- Scales with usage (B2B SaaS has variable workloads)
- Minimizes operational overhead (no DBA on staff)
- Keeps costs low during early stages
- Handles traffic spikes during demos/launches
- Integrates well with AWS infrastructure (VPC, Secrets Manager, IAM)

Options considered:
1. **Self-managed RDS PostgreSQL** - Full control, manual scaling, fixed costs
2. **Aurora Provisioned** - Managed, but fixed instance sizing
3. **Aurora Serverless v2** - Auto-scaling, pay-per-use
4. **Managed services (Supabase, PlanetScale)** - External dependency, data residency concerns

## Decision

Use **Aurora Serverless v2** with PostgreSQL compatibility.

## Rationale

### Cost-Effective Scaling

Aurora Serverless v2 scales in fine-grained increments (0.5 ACU):
```
Idle/Development:    0.5 ACU  (~$0.06/hour)
Normal traffic:      2-4 ACU  (~$0.24-0.48/hour)
Traffic spike:       Up to 16+ ACU (scales in seconds)
```

Compare to provisioned instances where you pay for peak capacity 24/7.

### Zero Capacity Planning

No need to predict instance sizes:
- Start small, scale automatically as customers onboard
- Handle demo days and launches without pre-provisioning
- Scale down during off-hours (B2B traffic is business hours)

### Operational Simplicity

AWS handles:
- Automatic patching and updates
- Storage scaling (up to 128 TiB)
- Continuous backups to S3
- Multi-AZ failover
- Performance Insights for monitoring

### RDS Proxy Integration

Connection pooling via RDS Proxy:
- Lambda functions share connection pool (no exhaustion)
- Handles failover transparently
- Reduces database load from connection churn

```
Lambda → RDS Proxy → Aurora Serverless
ECS    → RDS Proxy → Aurora Serverless
```

### PostgreSQL Compatibility

Full PostgreSQL feature set:
- JSON/JSONB for flexible schemas
- Full-text search capabilities
- Mature ecosystem and tooling
- Django ORM works unchanged

## Consequences

### Positive
- **Cost efficiency** - Pay only for compute used, not peak capacity
- **Automatic scaling** - No manual intervention for traffic changes
- **High availability** - Multi-AZ by default with fast failover
- **Managed operations** - AWS handles patches, backups, monitoring
- **Seamless integration** - Works with Secrets Manager, IAM, CloudWatch

### Negative
- **Cold start latency** - First query after idle may have 1-2s delay
- **Minimum cost floor** - 0.5 ACU minimum when not paused (~$43/month)
- **AWS lock-in** - Aurora-specific features don't port to vanilla PostgreSQL
- **Regional availability** - Not available in all regions

### Mitigations
- Keep minimum ACU at 0.5 to avoid cold starts (acceptable cost)
- Use standard PostgreSQL features where possible for portability
- RDS Proxy masks cold start latency for most queries
- Database abstraction via Django ORM eases potential migration

## Implementation Notes

### CDK Configuration
```python
database = rds.DatabaseCluster(
    self, "Database",
    engine=rds.DatabaseClusterEngine.aurora_postgres(
        version=rds.AuroraPostgresEngineVersion.VER_15_4
    ),
    serverless_v2_min_capacity=0.5,
    serverless_v2_max_capacity=16,
    writer=rds.ClusterInstance.serverless_v2("writer"),
    vpc=vpc,
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
)
```

### Capacity Planning Guidelines
| Stage | Min ACU | Max ACU | Est. Monthly |
|-------|---------|---------|--------------|
| Development | 0.5 | 2 | ~$50 |
| Early Production | 0.5 | 8 | ~$100-300 |
| Growth | 2 | 16 | ~$300-1000 |
| Scale | 4 | 32+ | $1000+ |

### Monitoring
- CloudWatch: `ServerlessDatabaseCapacity` metric
- Set alarms for sustained high ACU (indicates need for capacity review)
- Performance Insights for query-level analysis
