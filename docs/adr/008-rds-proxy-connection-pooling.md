# ADR 008: RDS Proxy for Connection Pooling

**Date:** January 18, 2026

## Context

Our architecture has multiple database clients:
- **ECS Fargate**: Web application (2-10 tasks, ~10 connections each)
- **Lambda functions**: Event publisher, audit log consumer, etc. (bursty, many concurrent)

Aurora Serverless v2 has connection limits:
- 0.5 ACU ≈ 45 connections
- 2 ACU ≈ 180 connections
- Scaling takes seconds, connection exhaustion is instant

Lambda is particularly problematic:
- Each invocation opens a new connection
- Connections may outlive the function (warm start reuse)
- Burst of events = burst of connections
- No built-in connection pooling

Options considered:
1. **Application-level pooling (PgBouncer sidecar)** - Adds complexity, still per-service pools
2. **Connection limits per service** - Fragile, hard to tune
3. **RDS Proxy** - AWS-managed, shared pool across all services
4. **Increase Aurora capacity** - Expensive, doesn't solve the problem

## Decision

Use **RDS Proxy** as the connection endpoint for all database clients.

## Rationale

### Unified Connection Pool

RDS Proxy multiplexes connections from all sources:
```
Lambda Function A ─┐
Lambda Function B ─┼─→ RDS Proxy (connection pool) ─→ Aurora (limited connections)
ECS Task 1 ────────┤
ECS Task 2 ────────┘
```

One managed pool instead of per-service pools.

### Lambda Connection Reuse

RDS Proxy pins connections for Lambda:
- First invocation: Get connection from pool
- Connection stays open for reuse
- Subsequent invocations reuse the same connection
- Proxy handles cleanup on idle timeout

No "connection leak" from Lambda cold starts.

### Transparent Failover

During Aurora failover:
- RDS Proxy holds client connections
- Reconnects to new writer automatically
- Application sees brief delay, not connection error

```python
# Before RDS Proxy: Connection error, must retry
# With RDS Proxy: Brief pause, then continues
cursor.execute("INSERT INTO orders ...")  # Transparently survives failover
```

### IAM Authentication

RDS Proxy supports IAM auth:
- No database credentials in Lambda environment
- Lambda role grants database access
- Credentials rotated automatically

```python
# Lambda with IAM auth
token = rds_client.generate_db_auth_token(
    DBHostname=proxy_endpoint,
    Port=5432,
    DBUsername="lambda_user",
)
connection = psycopg2.connect(host=proxy_endpoint, password=token, ...)
```

### Secrets Manager Integration

For username/password auth:
- RDS Proxy reads credentials from Secrets Manager
- Auto-rotates credentials without client changes
- Same secret for ECS and Lambda

## Consequences

### Positive
- **No connection exhaustion** - Proxy limits concurrent connections to Aurora
- **Lambda-friendly** - Built-in connection reuse for serverless
- **Simplified failover** - Applications don't need retry logic
- **Centralized auth** - One place for credential management
- **Monitoring** - CloudWatch metrics for pool utilization

### Negative
- **Added latency** - Extra network hop (~1ms typical)
- **Cost** - RDS Proxy pricing based on vCPU ($0.015/vCPU-hour)
- **Query restrictions** - Some PostgreSQL features not supported (e.g., prepared statements in some modes)
- **Debugging** - Another layer to troubleshoot

### Mitigations
- 1ms latency acceptable for our use case
- Cost is small relative to Aurora Serverless
- Use standard queries; avoid edge cases
- CloudWatch provides proxy-level metrics

## Implementation Notes

### CDK Configuration
```python
# RDS Proxy
rds_proxy = rds.DatabaseProxy(
    self, "DatabaseProxy",
    proxy_target=rds.ProxyTarget.from_cluster(database),
    secrets=[database_secret],
    vpc=vpc,
    security_groups=[database_security_group],
    require_tls=True,
    idle_client_timeout=Duration.minutes(30),
    max_connections_percent=90,  # Reserve 10% for admin
    max_idle_connections_percent=50,
)

# Grant Lambda access
rds_proxy.grant_connect(publisher_lambda, "app_user")
```

### Environment Variables
```bash
# ECS Task Definition
DATABASE_URL=postgresql://user:pass@proxy-endpoint:5432/dbname

# Lambda
RDS_PROXY_HOST=proxy-endpoint.proxy-xxxx.us-east-1.rds.amazonaws.com
DATABASE_SECRET_ARN=arn:aws:secretsmanager:...
```

### Django Settings
```python
# Works with RDS Proxy transparently
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("RDS_PROXY_HOST", "localhost"),
        "NAME": "pikaia",
        "USER": "app_user",
        "PASSWORD": os.environ.get("DATABASE_PASSWORD"),
        "PORT": 5432,
        "OPTIONS": {
            "sslmode": "require",  # RDS Proxy enforces TLS
        },
    }
}
```

### Lambda Handler
```python
# Lambda reuses connections automatically via RDS Proxy
import psycopg2
from functools import lru_cache

@lru_cache(maxsize=1)
def get_connection():
    """Cached connection, reused across warm invocations."""
    return psycopg2.connect(
        host=os.environ["RDS_PROXY_HOST"],
        database="pikaia",
        user="app_user",
        password=get_secret(),
        sslmode="require",
    )

def handler(event, context):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT ...")
```

### Monitoring
```python
# CloudWatch metrics for RDS Proxy
cloudwatch.Metric(
    namespace="AWS/RDS",
    metric_name="DatabaseConnections",
    dimensions_map={"ProxyName": proxy.db_proxy_name},
)

cloudwatch.Metric(
    namespace="AWS/RDS",
    metric_name="DatabaseConnectionsCurrentlySessionPinned",
    dimensions_map={"ProxyName": proxy.db_proxy_name},
)
```

### Connection Math
| Client | Max Concurrent | With Proxy |
|--------|---------------|------------|
| ECS (10 tasks × 10 conn) | 100 | Pooled |
| Lambda Publisher | 100 (burst) | Pooled |
| Lambda Audit | 100 (burst) | Pooled |
| **Total demand** | **300** | |
| **Aurora 0.5 ACU** | 45 limit | ✅ Proxy queues |
| **Aurora 2 ACU** | 180 limit | ✅ Proxy distributes |
