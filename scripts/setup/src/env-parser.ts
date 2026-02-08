import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import type { EnvConfig } from "./generators/env.js";

function parseEnvFile(filePath: string): Record<string, string> {
  if (!existsSync(filePath)) return {};
  const content = readFileSync(filePath, "utf-8");
  const vars: Record<string, string> = {};
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIndex = trimmed.indexOf("=");
    if (eqIndex === -1) continue;
    vars[trimmed.slice(0, eqIndex)] = trimmed.slice(eqIndex + 1);
  }
  return vars;
}

export function loadExistingServices(
  rootDir: string,
): EnvConfig["services"] {
  const backend = parseEnvFile(join(rootDir, "backend", ".env"));
  const frontend = parseEnvFile(join(rootDir, "frontend", ".env"));

  return {
    stytchProjectId: backend.STYTCH_PROJECT_ID || undefined,
    stytchSecret: backend.STYTCH_SECRET || undefined,
    stytchWebhookSecret: backend.STYTCH_WEBHOOK_SECRET || undefined,
    stytchPublicToken: frontend.VITE_STYTCH_PUBLIC_TOKEN || undefined,
    stripeSecretKey: backend.STRIPE_SECRET_KEY || undefined,
    stripePublishableKey: frontend.VITE_STRIPE_PUBLISHABLE_KEY || undefined,
    stripePriceId: backend.STRIPE_PRICE_ID || undefined,
    stripeWebhookSecret: backend.STRIPE_WEBHOOK_SECRET || undefined,
    resendApiKey: backend.RESEND_API_KEY || undefined,
    googlePlacesApiKey: frontend.VITE_GOOGLE_PLACES_API_KEY || undefined,
  };
}

export function loadExistingSecrets(
  rootDir: string,
): { djangoSecretKey?: string; fieldEncryptionKey?: string } {
  const backend = parseEnvFile(join(rootDir, "backend", ".env"));
  return {
    djangoSecretKey: backend.SECRET_KEY || undefined,
    fieldEncryptionKey: backend.FIELD_ENCRYPTION_KEY || undefined,
  };
}
