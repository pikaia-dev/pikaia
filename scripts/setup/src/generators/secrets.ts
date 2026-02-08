import { randomBytes, randomInt } from "node:crypto";

export function generateDjangoSecretKey(): string {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)";
  return Array.from({ length: 50 }, () => chars[randomInt(chars.length)]).join(
    "",
  );
}

export function generateFieldEncryptionKey(): string {
  return randomBytes(32).toString("base64");
}
