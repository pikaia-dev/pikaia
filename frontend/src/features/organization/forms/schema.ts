import { z } from "zod"

/**
 * Normalize a slug to meet Stytch requirements.
 * Allowed characters: a-z, 0-9, hyphen, period, underscore, tilde
 */
export function normalizeSlug(value: string): string {
    return value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9._~-]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 128)
}

/**
 * Schema for organization settings form.
 */
export const organizationSchema = z.object({
    name: z
        .string()
        .min(1, "Organization name is required")
        .max(255, "Name must be less than 255 characters"),
    slug: z
        .string()
        .min(2, "Slug must be at least 2 characters")
        .max(128, "Slug must be less than 128 characters")
        .regex(
            /^[a-z0-9._~-]+$/,
            "Only lowercase letters, numbers, hyphens, periods, underscores, and tildes allowed"
        ),
})

export type OrganizationFormData = z.infer<typeof organizationSchema>
