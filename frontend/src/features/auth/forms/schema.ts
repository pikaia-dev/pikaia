import { z } from 'zod'

/**
 * Schema for login email input.
 */
export const emailSchema = z.object({
  email: z.email('Please enter a valid email address'),
})

export type EmailFormData = z.infer<typeof emailSchema>
