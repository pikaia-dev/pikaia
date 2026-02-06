import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import type { BillingAddress } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { useUpdateBilling } from '@/features/organization/api/mutations'
import { useOrganization } from '@/features/organization/api/queries'
import { DEFAULT_COUNTRY } from '@/lib/countries'

/**
 * Card component for managing invoice delivery email settings.
 * Allows toggling a separate billing email address for invoices.
 */
export function InvoiceDeliveryForm() {
  const billingEmailRef = useRef<HTMLInputElement>(null)

  const { data: organization } = useOrganization()
  const updateBillingMutation = useUpdateBilling()

  const [useBillingEmail, setUseBillingEmail] = useState<boolean | null>(null)
  const [billingEmail, setBillingEmail] = useState<string | null>(null)
  const [savingDelivery, setSavingDelivery] = useState(false)

  const currentUseBillingEmail = useBillingEmail ?? organization?.billing.use_billing_email ?? false
  const currentBillingEmail = billingEmail ?? organization?.billing.billing_email ?? ''

  // Derive current values from server data for the full mutation payload
  const currentBillingName = organization?.billing.billing_name ?? ''
  const currentAddress: BillingAddress = {
    line1: organization?.billing.address.line1 ?? '',
    line2: organization?.billing.address.line2 ?? '',
    city: organization?.billing.address.city ?? '',
    state: organization?.billing.address.state ?? '',
    postal_code: organization?.billing.address.postal_code ?? '',
    country: organization?.billing.address.country || DEFAULT_COUNTRY,
  }
  const currentVatId = organization?.billing.vat_id ?? ''

  // Focus billing email input when checkbox is enabled
  useEffect(() => {
    if (currentUseBillingEmail) {
      billingEmailRef.current?.focus()
    }
  }, [currentUseBillingEmail])

  const handleDeliverySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSavingDelivery(true)
    try {
      await updateBillingMutation.mutateAsync({
        use_billing_email: currentUseBillingEmail,
        billing_email: currentUseBillingEmail ? currentBillingEmail : undefined,
        billing_name: currentBillingName,
        address: currentAddress,
        vat_id: currentVatId,
      })
      toast.success('Invoice delivery settings saved')
      setUseBillingEmail(null)
      setBillingEmail(null)
    } catch {
      // Error already handled by mutation
    } finally {
      setSavingDelivery(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Invoice Delivery</CardTitle>
        <CardDescription>Choose where to receive your invoices</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleDeliverySubmit} className="space-y-4">
          <div className="flex space-x-3">
            <Checkbox
              id="useBillingEmail"
              checked={currentUseBillingEmail}
              onCheckedChange={async (checked) => {
                const isChecked = checked === true
                setUseBillingEmail(isChecked)
                if (!isChecked) {
                  // Auto-save when unchecking since the form is hidden
                  setSavingDelivery(true)
                  try {
                    await updateBillingMutation.mutateAsync({
                      use_billing_email: false,
                      billing_email: '',
                      billing_name: currentBillingName,
                      address: currentAddress,
                      vat_id: currentVatId,
                    })
                    toast.success('Invoice delivery settings saved')
                    setUseBillingEmail(null)
                    setBillingEmail(null)
                  } catch {
                    // Revert on failure
                    setUseBillingEmail(true)
                  } finally {
                    setSavingDelivery(false)
                  }
                }
              }}
              className="mt-1"
            />
            <div className="space-y-1">
              <label
                htmlFor="useBillingEmail"
                className="text-sm font-medium leading-none cursor-pointer"
              >
                Send invoices to a different email
              </label>
              <p className="text-xs text-muted-foreground">
                By default, invoices are sent to the organization admin
              </p>
            </div>
          </div>

          {currentUseBillingEmail && (
            <>
              <div className="pl-7">
                <label htmlFor="billingEmail" className="block text-sm font-medium mb-1">
                  Billing email
                </label>
                <input
                  ref={billingEmailRef}
                  id="billingEmail"
                  type="email"
                  value={currentBillingEmail}
                  onChange={(e) => {
                    setBillingEmail(e.target.value)
                  }}
                  className="w-full max-w-sm px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="billing@company.com"
                  required
                />
              </div>
              <div className="pl-7">
                <Button type="submit" disabled={savingDelivery}>
                  {savingDelivery ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
