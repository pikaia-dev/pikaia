import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export interface SetupState {
  version: string;
  configured_at: string;
  project: {
    display_name: string;
    prefix: string;
    domain?: string;
    api_domain?: string;
  };
  services: {
    stytch: { configured: boolean };
    stripe: { configured: boolean };
    resend: { configured: boolean };
  };
  aws: {
    configured: boolean;
  };
}

const STATE_FILE = ".pikaia-setup.json";

export function getStatePath(rootDir: string): string {
  return join(rootDir, STATE_FILE);
}

export function loadState(rootDir: string): SetupState | null {
  const path = getStatePath(rootDir);
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf-8"));
}

export function saveState(rootDir: string, state: SetupState): void {
  const path = getStatePath(rootDir);
  writeFileSync(path, JSON.stringify(state, null, 2) + "\n");
}

export function createDefaultState(
  displayName: string,
  prefix: string,
): SetupState {
  return {
    version: "1.0.0",
    configured_at: new Date().toISOString(),
    project: {
      display_name: displayName,
      prefix,
    },
    services: {
      stytch: { configured: false },
      stripe: { configured: false },
      resend: { configured: false },
    },
    aws: {
      configured: false,
    },
  };
}
