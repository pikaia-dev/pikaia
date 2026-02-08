import * as p from "@clack/prompts";
import {
  validatePrefix,
  validateDisplayName,
  validateDomain,
  validateStytchProjectId,
  validateStytchSecret,
  validateStripeSecretKey,
  validateStripePublishableKey,
} from "./validators.js";
import type { SetupState } from "./state.js";

export interface BrandingAnswers {
  displayName: string;
  prefix: string;
}

export interface ServicesAnswers {
  stytchProjectId: string;
  stytchSecret: string;
  stytchPublicToken: string;
  stripeSecretKey: string;
  stripePublishableKey: string;
  resendApiKey: string;
  sentryDsn: string;
}

export interface AwsAnswers {
  domain: string;
  apiDomain: string;
  certificateArn: string;
}

export type SetupSection =
  | "branding"
  | "local"
  | "services"
  | "aws";

function exitOnCancel<T>(value: T | symbol): T {
  if (p.isCancel(value)) {
    p.cancel("Setup cancelled.");
    process.exit(0);
  }
  return value;
}

export async function promptSections(
  state: SetupState | null,
): Promise<SetupSection[]> {
  if (state) {
    p.note(
      `Project: ${state.project.display_name} (${state.project.prefix})`,
      "Existing configuration detected",
    );
  }

  const sections = exitOnCancel(
    await p.multiselect<
      { value: SetupSection; label: string; hint?: string }[],
      SetupSection
    >({
      message: "What would you like to configure?",
      options: [
        {
          value: "branding",
          label: "Project branding",
          hint: "name, resource prefix",
        },
        {
          value: "local",
          label: "Local development environment",
          hint: "generates .env files",
        },
        {
          value: "services",
          label: "Third-party services",
          hint: "Stytch, Stripe, Resend API keys",
        },
        {
          value: "aws",
          label: "AWS deployment",
          hint: "domain, CDK context, production secrets",
        },
      ],
      initialValues: state
        ? []
        : (["branding", "local"] as SetupSection[]),
    }),
  );

  return sections;
}

export async function promptBranding(
  defaults?: Partial<BrandingAnswers>,
): Promise<BrandingAnswers> {
  const displayName = exitOnCancel(
    await p.text({
      message: "Display name (shown in UI, emails, passkey prompts)",
      placeholder: "Acme Platform",
      defaultValue: defaults?.displayName,
      validate: validateDisplayName,
    }),
  );

  const suggestedPrefix =
    defaults?.prefix ||
    displayName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 28);

  const prefix = exitOnCancel(
    await p.text({
      message: "Resource prefix (lowercase, for AWS resources and database)",
      placeholder: suggestedPrefix,
      defaultValue: suggestedPrefix,
      validate: validatePrefix,
    }),
  );

  return { displayName, prefix };
}

export async function promptServices(
  defaults?: Partial<ServicesAnswers>,
): Promise<ServicesAnswers> {
  p.note(
    "Leave blank to skip — you can configure these later.",
    "Third-party services",
  );

  const stytchProjectId = exitOnCancel(
    await p.text({
      message: "Stytch Project ID",
      placeholder: "project-test-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      defaultValue: defaults?.stytchProjectId || "",
      validate: validateStytchProjectId,
    }),
  );

  const stytchSecret = exitOnCancel(
    await p.text({
      message: "Stytch Secret",
      placeholder: "secret-test-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      defaultValue: defaults?.stytchSecret || "",
      validate: validateStytchSecret,
    }),
  );

  const stytchPublicToken = exitOnCancel(
    await p.text({
      message: "Stytch Public Token (for frontend)",
      placeholder: "public-token-test-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      defaultValue: defaults?.stytchPublicToken || "",
    }),
  );

  const stripeSecretKey = exitOnCancel(
    await p.text({
      message: "Stripe Secret Key",
      placeholder: "sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      defaultValue: defaults?.stripeSecretKey || "",
      validate: validateStripeSecretKey,
    }),
  );

  const stripePublishableKey = exitOnCancel(
    await p.text({
      message: "Stripe Publishable Key (for frontend)",
      placeholder: "pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      defaultValue: defaults?.stripePublishableKey || "",
      validate: validateStripePublishableKey,
    }),
  );

  const resendApiKey = exitOnCancel(
    await p.text({
      message: "Resend API Key",
      placeholder: "re_xxxxxxxxxxxxxxxxxxxxxxxx",
      defaultValue: defaults?.resendApiKey || "",
    }),
  );

  const sentryDsn = exitOnCancel(
    await p.text({
      message: "Sentry DSN (for error tracking)",
      placeholder: "https://xxxx@o12345.ingest.us.sentry.io/12345",
      defaultValue: defaults?.sentryDsn || "",
    }),
  );

  return {
    stytchProjectId,
    stytchSecret,
    stytchPublicToken,
    stripeSecretKey,
    stripePublishableKey,
    resendApiKey,
    sentryDsn,
  };
}

export async function promptAws(
  defaults?: Partial<AwsAnswers>,
): Promise<AwsAnswers> {
  const domain = exitOnCancel(
    await p.text({
      message: "Frontend domain (where users access the app)",
      placeholder: "app.example.com",
      defaultValue: defaults?.domain,
      validate: validateDomain,
    }),
  );

  const parts = domain.split(".");
  const suggestedApiDomain =
    defaults?.apiDomain ||
    (parts.length > 2
      ? `api.${parts.slice(1).join(".")}`
      : `api.${domain}`);

  const apiDomain = exitOnCancel(
    await p.text({
      message: "API domain",
      placeholder: suggestedApiDomain,
      defaultValue: suggestedApiDomain,
      validate: validateDomain,
    }),
  );

  const certificateArn = exitOnCancel(
    await p.text({
      message: "ACM Certificate ARN (for HTTPS)",
      placeholder: "arn:aws:acm:us-east-1:123456789:certificate/xxx",
      defaultValue: defaults?.certificateArn || "",
    }),
  );

  return { domain, apiDomain, certificateArn };
}

export async function confirmOverwrite(files: string[]): Promise<boolean> {
  const result = exitOnCancel(
    await p.confirm({
      message: `Overwrite existing files?\n${files.map((f) => `  - ${f}`).join("\n")}`,
    }),
  );
  return result;
}
