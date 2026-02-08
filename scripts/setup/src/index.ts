import * as p from "@clack/prompts";
import pc from "picocolors";
import { existsSync } from "node:fs";
import { join, relative } from "node:path";
import { parseArgs } from "node:util";

import {
  loadState,
  saveState,
  createDefaultState,
  type SetupState,
} from "./state.js";
import {
  promptSections,
  promptBranding,
  promptServices,
  promptAws,
  confirmOverwrite,
  type SetupSection,
} from "./prompts.js";
import {
  generateBackendEnv,
  generateFrontendEnv,
  generateDockerEnv,
  generateProductionEnv,
  type EnvConfig,
} from "./generators/env.js";
import { generateCdkContext } from "./generators/cdk-context.js";
import {
  generateDjangoSecretKey,
  generateFieldEncryptionKey,
} from "./generators/secrets.js";

// --- CLI Argument Parsing ---

const { values: args, positionals } = parseArgs({
  options: {
    root: { type: "string", default: process.cwd() },
    ci: { type: "boolean", default: false },
    name: { type: "string" },
    prefix: { type: "string" },
    domain: { type: "string" },
    "api-domain": { type: "string" },
    yes: { type: "boolean", default: false },
    help: { type: "boolean", default: false },
  },
  allowPositionals: true,
  strict: false,
});

const ROOT_DIR = args.root as string;
const command = positionals[0] as string | undefined;

// --- Commands ---

function showHelp(): void {
  console.log(`
${pc.bold("Pikaia Setup")} — Configure your project

${pc.dim("Usage:")}
  ./scripts/setup/setup.sh [command] [options]

${pc.dim("Commands:")}
  ${pc.cyan("(default)")}     Interactive setup
  ${pc.cyan("branding")}      Project name and resource prefix
  ${pc.cyan("services")}      Third-party API keys (Stytch, Stripe, Resend)
  ${pc.cyan("aws")}           AWS deployment configuration
  ${pc.cyan("secrets")}       Regenerate secrets (Django key, encryption key)
  ${pc.cyan("status")}        Show current configuration
  ${pc.cyan("doctor")}        Check for common issues

${pc.dim("Options:")}
  --ci                Non-interactive mode (requires --name and --prefix)
  --name "App Name"   Display name
  --prefix "app"      Resource prefix
  --domain "app.com"  Production domain
  --api-domain "..."  API domain (default: api.<root-domain>)
  --yes               Accept defaults without prompting
  --help              Show this help
`);
}

function showStatus(state: SetupState | null): void {
  if (!state) {
    p.log.warning("No configuration found. Run setup first.");
    return;
  }

  p.intro(pc.bold("Current Configuration"));

  p.log.info(
    [
      `${pc.dim("Project:")}     ${state.project.display_name} (${state.project.prefix})`,
      state.project.domain
        ? `${pc.dim("Domain:")}      ${state.project.domain}`
        : null,
      state.project.api_domain
        ? `${pc.dim("API Domain:")}  ${state.project.api_domain}`
        : null,
      `${pc.dim("Configured:")}  ${new Date(state.configured_at).toLocaleDateString()}`,
      "",
      `${pc.dim("Services:")}`,
      `  Stytch:  ${state.services.stytch.configured ? pc.green("configured") : pc.yellow("not configured")}`,
      `  Stripe:  ${state.services.stripe.configured ? pc.green("configured") : pc.yellow("not configured")}`,
      `  Resend:  ${state.services.resend.configured ? pc.green("configured") : pc.yellow("not configured")}`,
      "",
      `  AWS:     ${state.aws.configured ? pc.green("configured") : pc.yellow("not configured")}`,
    ]
      .filter(Boolean)
      .join("\n"),
  );
}

function runDoctor(): void {
  p.intro(pc.bold("Doctor"));
  let issues = 0;

  const checks: Array<{ name: string; path: string; required: boolean }> = [
    { name: "Backend .env", path: "backend/.env", required: true },
    { name: "Frontend .env", path: "frontend/.env", required: true },
    { name: "Docker .env.local", path: ".env.local", required: false },
    { name: "CDK context", path: "infra/cdk.context.json", required: false },
    {
      name: "Production secrets",
      path: ".env.production",
      required: false,
    },
  ];

  for (const check of checks) {
    const exists = existsSync(join(ROOT_DIR, check.path));
    if (exists) {
      p.log.success(`${check.name}: ${pc.green("found")}`);
    } else if (check.required) {
      p.log.error(`${check.name}: ${pc.red("missing")} — run setup to generate`);
      issues++;
    } else {
      p.log.warning(
        `${check.name}: ${pc.yellow("missing")} — optional, run setup with AWS section to generate`,
      );
    }
  }

  // Check Node.js version
  const nodeVersion = parseInt(process.versions.node.split(".")[0]);
  if (nodeVersion >= 20) {
    p.log.success(`Node.js: ${pc.green(`v${process.versions.node}`)}`);
  } else {
    p.log.error(`Node.js: ${pc.red(`v${process.versions.node}`)} — 20+ required`);
    issues++;
  }

  // Check for PostgreSQL
  const pgDir = join(ROOT_DIR, "backend");
  if (existsSync(pgDir)) {
    p.log.success(`Backend directory: ${pc.green("found")}`);
  } else {
    p.log.error(`Backend directory: ${pc.red("missing")}`);
    issues++;
  }

  if (issues === 0) {
    p.outro(pc.green("All checks passed!"));
  } else {
    p.outro(pc.yellow(`${issues} issue(s) found`));
  }
}

// --- Main Flow ---

function relPath(absPath: string): string {
  return relative(ROOT_DIR, absPath);
}

async function runCiMode(): Promise<void> {
  const displayName = args.name as string;
  const prefix = args.prefix as string;

  if (!displayName || !prefix) {
    console.error("Error: --ci mode requires --name and --prefix");
    process.exit(1);
  }

  const config: EnvConfig = {
    project: {
      displayName,
      prefix,
      domain: args.domain as string | undefined,
      apiDomain: args["api-domain"] as string | undefined,
    },
    secrets: {
      djangoSecretKey: generateDjangoSecretKey(),
      fieldEncryptionKey: generateFieldEncryptionKey(),
    },
    services: {},
  };

  const generated: string[] = [];
  generated.push(relPath(generateBackendEnv(ROOT_DIR, config)));
  generated.push(relPath(generateFrontendEnv(ROOT_DIR, config)));
  generated.push(relPath(generateDockerEnv(ROOT_DIR, config)));

  if (config.project.domain) {
    generated.push(relPath(generateProductionEnv(ROOT_DIR, config)));
    generated.push(
      relPath(
        generateCdkContext(ROOT_DIR, {
          prefix,
          domain: config.project.domain,
          apiDomain: config.project.apiDomain,
        }),
      ),
    );
  }

  const state = createDefaultState(displayName, prefix);
  if (config.project.domain) {
    state.project.domain = config.project.domain;
    state.project.api_domain = config.project.apiDomain;
    state.aws.configured = true;
  }
  saveState(ROOT_DIR, state);

  for (const file of generated) {
    console.log(`  generated: ${file}`);
  }
}

async function runInteractive(sections?: SetupSection[]): Promise<void> {
  p.intro(pc.bold("Pikaia Setup"));

  const state = loadState(ROOT_DIR);

  // Determine which sections to configure
  const selectedSections = sections || (await promptSections(state));

  let displayName = state?.project.display_name || "";
  let prefix = state?.project.prefix || "";
  let domain = state?.project.domain;
  let apiDomain = state?.project.api_domain;
  let certificateArn: string | undefined;
  let services: Partial<EnvConfig["services"]> = {};

  // --- Branding ---
  if (selectedSections.includes("branding")) {
    const branding = await promptBranding({
      displayName: state?.project.display_name,
      prefix: state?.project.prefix,
    });
    displayName = branding.displayName;
    prefix = branding.prefix;
  } else if (!displayName || !prefix) {
    // Branding is required for first run
    p.log.warning("Project branding is required for first-time setup.");
    const branding = await promptBranding();
    displayName = branding.displayName;
    prefix = branding.prefix;
  }

  // --- Services ---
  if (selectedSections.includes("services")) {
    services = await promptServices();
  }

  // --- AWS ---
  if (selectedSections.includes("aws")) {
    const aws = await promptAws({
      domain: state?.project.domain,
      apiDomain: state?.project.api_domain,
    });
    domain = aws.domain;
    apiDomain = aws.apiDomain;
    certificateArn = aws.certificateArn || undefined;
  }

  // --- Generate Files ---
  const config: EnvConfig = {
    project: { displayName, prefix, domain, apiDomain },
    secrets: {
      djangoSecretKey: generateDjangoSecretKey(),
      fieldEncryptionKey: generateFieldEncryptionKey(),
    },
    services,
  };

  // Check for existing files
  const filesToGenerate: string[] = [];
  if (
    selectedSections.includes("branding") ||
    selectedSections.includes("local") ||
    selectedSections.includes("services")
  ) {
    filesToGenerate.push("backend/.env", "frontend/.env", ".env.local");
  }
  if (selectedSections.includes("aws")) {
    filesToGenerate.push(".env.production", "infra/cdk.context.json");
  }

  const existingFiles = filesToGenerate.filter((f) =>
    existsSync(join(ROOT_DIR, f)),
  );

  if (existingFiles.length > 0) {
    const shouldOverwrite = await confirmOverwrite(existingFiles);
    if (!shouldOverwrite) {
      p.cancel("Setup cancelled — no files were modified.");
      process.exit(0);
    }
  }

  // Generate
  const s = p.spinner();
  s.start("Generating configuration...");

  const generated: string[] = [];

  if (
    selectedSections.includes("branding") ||
    selectedSections.includes("local") ||
    selectedSections.includes("services")
  ) {
    generated.push(relPath(generateBackendEnv(ROOT_DIR, config)));
    generated.push(relPath(generateFrontendEnv(ROOT_DIR, config)));
    generated.push(relPath(generateDockerEnv(ROOT_DIR, config)));
  }

  if (selectedSections.includes("aws") && domain) {
    generated.push(relPath(generateProductionEnv(ROOT_DIR, config)));
    generated.push(
      relPath(
        generateCdkContext(ROOT_DIR, {
          prefix,
          domain,
          apiDomain,
          certificateArn,
        }),
      ),
    );
  }

  s.stop("Configuration generated!");

  // Show generated files
  for (const file of generated) {
    p.log.success(file);
  }

  // --- Update State ---
  const newState = state || createDefaultState(displayName, prefix);
  newState.configured_at = new Date().toISOString();
  newState.project.display_name = displayName;
  newState.project.prefix = prefix;

  if (selectedSections.includes("services")) {
    newState.services.stytch.configured = !!services.stytchProjectId;
    newState.services.stripe.configured = !!services.stripeSecretKey;
    newState.services.resend.configured = !!services.resendApiKey;
  }

  if (selectedSections.includes("aws") && domain) {
    newState.project.domain = domain;
    newState.project.api_domain = apiDomain;
    newState.aws.configured = true;
  }

  saveState(ROOT_DIR, newState);

  // --- Next Steps ---
  const nextSteps = [
    "Start local dev:  docker compose up -d && cd backend && uv run python manage.py migrate && uv run python manage.py runserver",
  ];

  if (!newState.services.stytch.configured) {
    nextSteps.push(
      "Configure Stytch:  ./scripts/setup/setup.sh services",
    );
  }

  if (!newState.aws.configured) {
    nextSteps.push(
      "Prepare deployment: ./scripts/setup/setup.sh aws",
    );
  }

  p.note(nextSteps.join("\n"), "Next steps");
  p.outro(pc.green("Setup complete!"));
}

async function regenerateSecrets(): Promise<void> {
  p.intro(pc.bold("Regenerate Secrets"));

  const state = loadState(ROOT_DIR);
  if (!state) {
    p.log.error(
      "No configuration found. Run setup first to configure branding.",
    );
    process.exit(1);
  }

  const confirmed = await confirmOverwrite(["backend/.env (SECRET_KEY, FIELD_ENCRYPTION_KEY)"]);
  if (!confirmed) {
    p.cancel("Cancelled.");
    process.exit(0);
  }

  const config: EnvConfig = {
    project: {
      displayName: state.project.display_name,
      prefix: state.project.prefix,
      domain: state.project.domain,
      apiDomain: state.project.api_domain,
    },
    secrets: {
      djangoSecretKey: generateDjangoSecretKey(),
      fieldEncryptionKey: generateFieldEncryptionKey(),
    },
    services: {},
  };

  generateBackendEnv(ROOT_DIR, config);
  p.log.success("backend/.env regenerated with new secrets");

  if (state.aws.configured) {
    generateProductionEnv(ROOT_DIR, config);
    p.log.success(".env.production regenerated with new secrets");
  }

  p.outro(pc.green("Secrets regenerated!"));
}

// --- Entry Point ---

async function main(): Promise<void> {
  if (args.help) {
    showHelp();
    process.exit(0);
  }

  if (args.ci) {
    await runCiMode();
    return;
  }

  switch (command) {
    case "branding":
      await runInteractive(["branding", "local"]);
      break;
    case "services":
      await runInteractive(["services"]);
      break;
    case "aws":
      await runInteractive(["aws"]);
      break;
    case "secrets":
      await regenerateSecrets();
      break;
    case "status":
      showStatus(loadState(ROOT_DIR));
      break;
    case "doctor":
      runDoctor();
      break;
    case "help":
      showHelp();
      break;
    case undefined:
      await runInteractive();
      break;
    default:
      console.error(`Unknown command: ${command}`);
      showHelp();
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
