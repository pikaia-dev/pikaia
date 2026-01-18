import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { AddressAutocomplete } from '../../components/ui/address-autocomplete'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { Checkbox } from '../../components/ui/checkbox'
import { CountryCombobox } from '../../components/ui/country-combobox'
import { LoadingSpinner } from '../../components/ui/loading-spinner'
import { InvoiceHistoryCard, SubscriptionCard } from '../../features/billing/components'
import { useInvoices, useSubscription } from '../../features/billing/queries'
import { useOrganization, useUpdateBilling } from '../../features/organization/queries'
import type { BillingAddress, Invoice } from '../../lib/api'
import {
  DEFAULT_COUNTRY,
  getPostalCodeLabel,
  getStateLabel,
  getVatPrefix,
  shouldShowTaxId,
  updateVatIdForCountryChange,
} from '../../lib/countries'
import type { ParsedAddress } from '../../lib/google-places'

export default function BillingSettings() {
  const billingEmailRef = useRef<HTMLInputElement>(null)

  // Queries
  const { data: organization, isLoading: orgLoading } = useOrganization()
  const { data: subscription, isLoading: subLoading } = useSubscription()
  const { data: invoicesData, isLoading: invoicesLoading } = useInvoices({
    limit: 6,
  })

  // Mutations
  const updateBillingMutation = useUpdateBilling()

  // Form state (editable fields)
  const [useBillingEmail, setUseBillingEmail] = useState<boolean | null>(null)
  const [billingEmail, setBillingEmail] = useState<string | null>(null)
  const [billingName, setBillingName] = useState<string | null>(null)
  const [address, setAddress] = useState<BillingAddress | null>(null)
  const [vatId, setVatId] = useState<string | null>(null)
  const [savingDelivery, setSavingDelivery] = useState(false)
  const [savingAddress, setSavingAddress] = useState(false)

  // Invoice pagination state (additional invoices beyond first page)
  const [additionalInvoices, setAdditionalInvoices] = useState<Invoice[]>([])
  const [invoicesHasMore, setInvoicesHasMore] = useState(false)
  const [loadingMoreInvoices, setLoadingMoreInvoices] = useState(false)

  // Derived values from server data or edited values
  const currentUseBillingEmail = useBillingEmail ?? organization?.billing.use_billing_email ?? false
  const currentBillingEmail = billingEmail ?? organization?.billing.billing_email ?? ''
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

  // Update invoices pagination state when data changes
  useEffect(() => {
    if (invoicesData) {
      setInvoicesHasMore(invoicesData.has_more)
    }
  }, [invoicesData])

  // Combine base invoices with additional loaded invoices
  const allInvoices = [...(invoicesData?.invoices ?? []), ...additionalInvoices]

  // Focus billing email input when checkbox is enabled
  useEffect(() => {
    if (currentUseBillingEmail) {
      billingEmailRef.current?.focus()
    }
  }, [currentUseBillingEmail])

  const loadMoreInvoices = async () => {
    if (!allInvoices.length || loadingMoreInvoices) return
    setLoadingMoreInvoices(true)
    try {
      const lastInvoice = allInvoices[allInvoices.length - 1]
      const session = localStorage.getItem('stytch_session_jwt') ?? ''
      const response = await fetch(
        `/api/v1/billing/invoices?limit=6&starting_after=${lastInvoice.id}`,
        {
          headers: {
            Authorization: `Bearer ${session}`,
          },
        }
      )
      if (!response.ok) throw new Error('Failed to load more invoices')
      const data = (await response.json()) as {
        invoices: Invoice[]
        has_more: boolean
      }
      setAdditionalInvoices((prev) => [...prev, ...data.invoices])
      setInvoicesHasMore(data.has_more)
    } catch {
      toast.error('Failed to load more invoices')
    } finally {
      setLoadingMoreInvoices(false)
    }
  }

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
      // Reset edit state
      setUseBillingEmail(null)
      setBillingEmail(null)
    } catch {
      // Error already handled by mutation
    } finally {
      setSavingDelivery(false)
    }
  }

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
      // Reset edit state
      setBillingName(null)
      setAddress(null)
      setVatId(null)
    } catch {
      // Error already handled by mutation
    } finally {
      setSavingAddress(false)
    }
  }

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

  const isLoading = orgLoading || subLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  const isSubscribed = subscription && subscription.status !== 'none'
  const memberCount = subscription?.quantity || 1

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Billing</h1>
        <p className="text-muted-foreground">Manage billing information for invoices</p>
      </div>

      <div className="space-y-6 max-w-2xl">
        {/* Subscription Status Card */}
        <SubscriptionCard subscription={subscription ?? null} memberCount={memberCount} />

        {/* Invoice Delivery Card */}
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

        {/* Billing Address Card */}
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
                <p className="text-xs text-muted-foreground mt-1">
                  Type to search or enter manually
                </p>
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

        {/* Invoice History Card - show only when subscribed */}
        {isSubscribed && (
          <InvoiceHistoryCard
            invoices={allInvoices}
            isLoading={invoicesLoading}
            hasMore={invoicesHasMore}
            loadingMore={loadingMoreInvoices}
            onLoadMore={loadMoreInvoices}
          />
        )}
      </div>
    </div>
  )
}
