import { writeFileSync } from "node:fs";
import { join } from "node:path";

export interface CdkContextConfig {
  prefix: string;
  domain?: string;
  apiDomain?: string;
  certificateArn?: string;
}

export function generateCdkContext(
  rootDir: string,
  config: CdkContextConfig,
): string {
  const filePath = join(rootDir, "infra", "cdk.context.json");

  const context: Record<string, string> = {
    resource_prefix: config.prefix,
    ecr_repository_name: `${config.prefix}-backend`,
    secrets_path: `${config.prefix}/app-secrets`,
    database_name: config.prefix,
    event_bus_name: `${config.prefix}-events`,
    alarm_topic_name: `${config.prefix}-alarms`,
    dashboard_name: `${config.prefix}-operations`,
    frontend_bucket_prefix: `${config.prefix}-frontend`,
    log_stream_prefix: `${config.prefix}-backend`,
  };

  if (config.domain) {
    context.frontend_domain = config.domain;
  }
  if (config.apiDomain) {
    context.domain_name = config.apiDomain;
  }
  if (config.certificateArn) {
    context.certificate_arn = config.certificateArn;
  }

  writeFileSync(filePath, JSON.stringify(context, null, 2) + "\n");
  return filePath;
}
