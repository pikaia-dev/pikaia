import { useCallback, useState } from 'react'
import { toast } from 'sonner'
import type { BillingAddress } from '@/api/types'
import { AddressAutocomplete } from '@/components/ui/address-autocomplete'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CountryCombobox } from '@/components/ui/country-combobox'
import { useUpdateBilling } from '@/features/organization/api/mutations'
import { useOrganization } from '@/features/organization/api/queries'
import {
  DEFAULT_COUNTRY,
  getPostalCodeLabel,
  getStateLabel,
  getVatPrefix,
  shouldShowTaxId,
  updateVatIdForCountryChange,
} from '@/lib/countries'
import type { ParsedAddress } from '@/lib/google-places'

/**
 * Card component for managing billing address, company name, and VAT ID.
 * Includes Google Places autocomplete for address entry.
 */
export function BillingAddressForm() {
  const { data: organization } = useOrganization()
  const updateBillingMutation = useUpdateBilling()

  const [billingName, setBillingName] = useState<string | null>(null)
  const [address, setAddress] = useState<BillingAddress | null>(null)
  const [vatId, setVatId] = useState<string | null>(null)
  const [savingAddress, setSavingAddress] = useState(false)

  const currentBillingName = billingName ?? organization?.billing.billing_name ?? ''
  const currentAddress = address ?? {
    line1: organization?.billing.address.line1 ?? '',
    line2: organization?.billing.address.line2 ?? '',
    city: organization?.billing.address.city ?? '',
    state: organization?.billing.address.state ?? '',
    postal_code: organization?.billing.address.postal_code ?? '',
    country: organization?.billing.address.country || DEFAULT_COUNTRY,
  }
  const currentVatId = vatId ?? organization?.billing.vat_id ?? ''

  // Derive current delivery values from server data for the full mutation payload
  const currentUseBillingEmail = organization?.billing.use_billing_email ?? false
  const currentBillingEmail = organization?.billing.billing_email ?? ''

  const updateAddress = (field: keyof BillingAddress, value: string) => {
    const previousCountry = currentAddress.country
    setAddress((prev) => ({
      ...(prev ?? currentAddress),
      [field]: value,
    }))

    // When country changes, update VAT prefix if EU country
    if (field === 'country') {
      setVatId((currentVat) =>
        updateVatIdForCountryChange(currentVat ?? currentVatId, previousCountry, value)
      )
    }
  }

  // Handle address selection from Google Places autocomplete
  const handleAddressSelect = useCallback(
    (parsed: ParsedAddress) => {
      const previousCountry = currentAddress.country
      // Update address fields from parsed Google Places result
      setAddress({
        line1: parsed.street_address || parsed.formatted_address,
        line2: '', // User can fill manually if needed
        city: parsed.city,
        state: parsed.state,
        postal_code: parsed.postal_code,
        country: parsed.country_code.toUpperCase(),
      })

      // Trigger VAT prefix update for the new country
      const countryCode = parsed.country_code.toUpperCase()
      setVatId((currentVat) =>
        updateVatIdForCountryChange(currentVat ?? currentVatId, previousCountry, countryCode)
      )
    },
    [currentAddress.country, currentVatId]
  )

  // Get current VAT prefix based on country
  const currentVatPrefix = getVatPrefix(currentAddress.country)

  const handleAddressSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSavingAddress(true)
    try {
      await updateBillingMutation.mutateAsync({
        use_billing_email: currentUseBillingEmail,
        billing_email: currentUseBillingEmail ? currentBillingEmail : undefined,
        billing_name: currentBillingName,
        address: currentAddress,
        vat_id: currentVatId,
      })
      toast.success('Billing address saved')
      setBillingName(null)
      setAddress(null)
      setVatId(null)
    } catch {
      // Error already handled by mutation
    } finally {
      setSavingAddress(false)
    }
  }

  return (
    <Card>
      <form onSubmit={handleAddressSubmit}>
        <CardHeader>
          <CardTitle className="text-base">Billing Address</CardTitle>
          <CardDescription>This information will appear on your invoices</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label htmlFor="billingName" className="block text-sm font-medium mb-1">
              Legal / company name
            </label>
            <input
              id="billingName"
              type="text"
              value={currentBillingName}
              onChange={(e) => {
                setBillingName(e.target.value)
              }}
              className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Acme Corporation Inc."
            />
          </div>

          {/* Street Address with autocomplete */}
          <div>
            <label htmlFor="line1" className="block text-sm font-medium mb-1">
              Street Address
            </label>
            <AddressAutocomplete
              id="line1"
              value={currentAddress.line1}
              onChange={(value) => {
                updateAddress('line1', value)
              }}
              onAddressSelect={handleAddressSelect}
              placeholder="Start typing to search..."
            />
            <p className="text-xs text-muted-foreground mt-1">Type to search or enter manually</p>
          </div>

          {/* Address Line 2 */}
          <div>
            <label htmlFor="line2" className="block text-sm font-medium mb-1">
              Address Line 2
            </label>
            <input
              id="line2"
              type="text"
              value={currentAddress.line2}
              onChange={(e) => {
                updateAddress('line2', e.target.value)
              }}
              className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Apt, Suite, Floor (optional)"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="city" className="block text-sm font-medium mb-1">
                City
              </label>
              <input
                id="city"
                type="text"
                value={currentAddress.city}
                onChange={(e) => {
                  updateAddress('city', e.target.value)
                }}
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div>
              <label htmlFor="state" className="block text-sm font-medium mb-1">
                {getStateLabel(currentAddress.country)}
              </label>
              <input
                id="state"
                type="text"
                value={currentAddress.state}
                onChange={(e) => {
                  updateAddress('state', e.target.value)
                }}
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div>
              <label htmlFor="postalCode" className="block text-sm font-medium mb-1">
                {getPostalCodeLabel(currentAddress.country)}
              </label>
              <input
                id="postalCode"
                type="text"
                value={currentAddress.postal_code}
                onChange={(e) => {
                  updateAddress('postal_code', e.target.value)
                }}
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="country" className="block text-sm font-medium mb-1">
                Country
              </label>
              <CountryCombobox
                value={currentAddress.country}
                onValueChange={(value) => {
                  updateAddress('country', value)
                }}
                placeholder="Select country..."
              />
            </div>

            {shouldShowTaxId(currentAddress.country) && (
              <div>
                <label htmlFor="vatId" className="block text-sm font-medium mb-1">
                  VAT ID
                </label>
                {currentVatPrefix ? (
                  <div className="flex">
                    <span className="inline-flex items-center px-3 py-2 border border-r-0 border-border rounded-l-md bg-muted text-sm text-muted-foreground">
                      {currentVatPrefix}
                    </span>
                    <input
                      id="vatId"
                      type="text"
                      value={
                        currentVatId.startsWith(currentVatPrefix)
                          ? currentVatId.slice(currentVatPrefix.length)
                          : currentVatId
                      }
                      onChange={(e) => {
                        setVatId(currentVatPrefix + e.target.value)
                      }}
                      className="flex-1 px-3 py-2 border border-border rounded-r-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      placeholder="123456789"
                    />
                  </div>
                ) : (
                  <input
                    id="vatId"
                    type="text"
                    value={currentVatId}
                    onChange={(e) => {
                      setVatId(e.target.value)
                    }}
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Enter VAT ID"
                  />
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  {currentVatPrefix ? 'EU VAT number for tax exemption' : 'VAT ID (optional)'}
                </p>
              </div>
            )}
          </div>

          <Button type="submit" disabled={savingAddress}>
            {savingAddress ? 'Saving...' : 'Save billing info'}
          </Button>
        </CardContent>
      </form>
    </Card>
  )
}
