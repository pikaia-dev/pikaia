import { z } from 'zod'

/**
 * Schema for member invitation form.
 */
export const inviteMemberSchema = z.object({
  email: z.email('Please enter a valid email address'),
  name: z.string().max(255, 'Name must be less than 255 characters').optional(),
  role: z.enum(['admin', 'member']),
})

export type InviteMemberFormData = z.infer<typeof inviteMemberSchema>
