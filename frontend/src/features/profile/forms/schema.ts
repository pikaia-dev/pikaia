import { z } from 'zod'

/**
 * Schema for profile name update.
 */
export const profileNameSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255, 'Name must be less than 255 characters'),
})

export type ProfileNameFormData = z.infer<typeof profileNameSchema>

/**
 * Schema for email update.
 */
export const emailUpdateSchema = z.object({
  email: z.email('Please enter a valid email address'),
})

export type EmailUpdateFormData = z.infer<typeof emailUpdateSchema>

/**
 * Schema for phone OTP verification.
 */
export const phoneOtpSchema = z.object({
  otp_code: z
    .string()
    .length(6, 'Verification code must be 6 digits')
    .regex(/^\d+$/, 'Only digits allowed'),
})

export type PhoneOtpFormData = z.infer<typeof phoneOtpSchema>
