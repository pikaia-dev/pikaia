export function validatePrefix(value: string): string | undefined {
  if (!value.trim()) return "Resource prefix is required";
  if (!/^[a-z][a-z0-9-]*$/.test(value)) {
    return "Must start with a letter and contain only lowercase letters, numbers, and hyphens";
  }
  if (value.length < 2 || value.length > 28) {
    return "Must be 2-28 characters (AWS resource name limits)";
  }
  return undefined;
}

export function validateDomain(value: string): string | undefined {
  if (!value.trim()) return "Domain is required";
  if (
    !/^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$/.test(
      value,
    )
  ) {
    return "Must be a valid domain (e.g., app.example.com)";
  }
  return undefined;
}

export function validateDisplayName(value: string): string | undefined {
  if (!value.trim()) return "Display name is required";
  return undefined;
}

export function validateStytchProjectId(value: string): string | undefined {
  if (value && !value.startsWith("project-")) {
    return 'Stytch Project ID should start with "project-"';
  }
  return undefined;
}

export function validateStytchSecret(value: string): string | undefined {
  if (value && !value.startsWith("secret-")) {
    return 'Stytch Secret should start with "secret-"';
  }
  return undefined;
}

export function validateStripeSecretKey(value: string): string | undefined {
  if (value && !value.startsWith("sk_test_") && !value.startsWith("sk_live_")) {
    return 'Stripe Secret Key should start with "sk_test_" or "sk_live_"';
  }
  return undefined;
}

export function validateStripePublishableKey(
  value: string,
): string | undefined {
  if (value && !value.startsWith("pk_test_") && !value.startsWith("pk_live_")) {
    return 'Stripe Publishable Key should start with "pk_test_" or "pk_live_"';
  }
  return undefined;
}
