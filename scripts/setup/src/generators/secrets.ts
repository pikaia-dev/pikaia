import { randomBytes } from "node:crypto";

export function generateDjangoSecretKey(): string {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)";
  const bytes = randomBytes(50);
  return Array.from(bytes)
    .map((b) => chars[b % chars.length])
    .join("");
}

export function generateFieldEncryptionKey(): string {
  return randomBytes(32).toString("base64");
}
