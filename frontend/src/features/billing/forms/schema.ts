import { z } from 'zod'

/**
 * Schema for invoice delivery settings.
 */
export const invoiceDeliverySchema = z
  .object({
    use_billing_email: z.boolean(),
    billing_email: z.string().optional(),
  })
  .refine(
    (data) => {
      // If use_billing_email is true, billing_email must be a valid email
      if (data.use_billing_email) {
        return data.billing_email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.billing_email)
      }
      return true
    },
    {
      message: 'Please enter a valid billing email',
      path: ['billing_email'],
    }
  )

export type InvoiceDeliveryFormData = z.infer<typeof invoiceDeliverySchema>

/**
 * Schema for billing address.
 */
export const billingAddressSchema = z.object({
  billing_name: z.string().max(255, 'Company name must be less than 255 characters').optional(),
  line1: z.string().max(255, 'Address line 1 too long').optional(),
  line2: z.string().max(255, 'Address line 2 too long').optional(),
  city: z.string().max(100, 'City name too long').optional(),
  state: z.string().max(100, 'State name too long').optional(),
  postal_code: z.string().max(20, 'Postal code too long').optional(),
  country: z.string().length(2, 'Country code must be 2 characters').optional(),
  vat_id: z.string().max(50, 'VAT ID too long').optional(),
})

export type BillingAddressFormData = z.infer<typeof billingAddressSchema>
