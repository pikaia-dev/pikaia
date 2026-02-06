import { zodResolver } from '@hookform/resolvers/zod'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import type { Invoice } from '@/api/types'
import { AddressAutocomplete } from '@/components/ui/address-autocomplete'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { CountryCombobox } from '@/components/ui/country-combobox'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useInvoices, useSubscription } from '@/features/billing/api/queries'
import { InvoiceHistoryCard } from '@/features/billing/components/invoice-history-card'
import { SubscriptionCard } from '@/features/billing/components/subscription-card'
import type {
  BillingAddressFormData,
  InvoiceDeliveryFormData,
} from '@/features/billing/forms/schema'
import { billingAddressSchema, invoiceDeliverySchema } from '@/features/billing/forms/schema'
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

  // Invoice delivery form (useForm + zodResolver)
  const deliveryForm = useForm<InvoiceDeliveryFormData>({
    resolver: zodResolver(invoiceDeliverySchema),
    defaultValues: {
      use_billing_email: false,
      billing_email: '',
    },
  })

  // Billing address form (useForm + zodResolver)
  const addressForm = useForm<BillingAddressFormData>({
    resolver: zodResolver(billingAddressSchema),
    defaultValues: {
      billing_name: '',
      line1: '',
      line2: '',
      city: '',
      state: '',
      postal_code: '',
      country: DEFAULT_COUNTRY,
      vat_id: '',
    },
  })

  const [savingDelivery, setSavingDelivery] = useState(false)
  const [savingAddress, setSavingAddress] = useState(false)

  // Invoice pagination state (additional invoices beyond first page)
  const [additionalInvoices, setAdditionalInvoices] = useState<Invoice[]>([])
  const [invoicesHasMore, setInvoicesHasMore] = useState(false)
  const [loadingMoreInvoices, setLoadingMoreInvoices] = useState(false)

  // Derived values from form state
  const currentUseBillingEmail = deliveryForm.watch('use_billing_email')
  const currentBillingEmail = deliveryForm.watch('billing_email') ?? ''
  const currentBillingName = addressForm.watch('billing_name') ?? ''
  const currentAddress = {
    line1: addressForm.watch('line1') ?? '',
    line2: addressForm.watch('line2') ?? '',
    city: addressForm.watch('city') ?? '',
    state: addressForm.watch('state') ?? '',
    postal_code: addressForm.watch('postal_code') ?? '',
    country: addressForm.watch('country') || DEFAULT_COUNTRY,
  }
  const currentVatId = addressForm.watch('vat_id') ?? ''

  // Sync forms with server data when it loads
  useEffect(() => {
    if (organization) {
      deliveryForm.reset({
        use_billing_email: organization.billing.use_billing_email,
        billing_email: organization.billing.billing_email ?? '',
      })
      addressForm.reset({
        billing_name: organization.billing.billing_name ?? '',
        line1: organization.billing.address.line1 ?? '',
        line2: organization.billing.address.line2 ?? '',
        city: organization.billing.address.city ?? '',
        state: organization.billing.address.state ?? '',
        postal_code: organization.billing.address.postal_code ?? '',
        country: organization.billing.address.country || DEFAULT_COUNTRY,
        vat_id: organization.billing.vat_id ?? '',
      })
    }
  }, [organization, deliveryForm.reset, addressForm.reset])

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

  const handleDeliverySubmit = deliveryForm.handleSubmit(async (data) => {
    setSavingDelivery(true)
    try {
      await updateBillingMutation.mutateAsync({
        use_billing_email: data.use_billing_email,
        billing_email: data.use_billing_email ? data.billing_email : undefined,
        billing_name: currentBillingName,
        address: currentAddress,
        vat_id: currentVatId,
      })
      toast.success('Invoice delivery settings saved')
    } catch {
      // Error already handled by mutation
    } finally {
      setSavingDelivery(false)
    }
  })

  const handleAddressSubmit = addressForm.handleSubmit(async (data) => {
    setSavingAddress(true)
    try {
      await updateBillingMutation.mutateAsync({
        use_billing_email: currentUseBillingEmail,
        billing_email: currentUseBillingEmail ? currentBillingEmail : undefined,
        billing_name: data.billing_name,
        address: {
          line1: data.line1 ?? '',
          line2: data.line2 ?? '',
          city: data.city ?? '',
          state: data.state ?? '',
          postal_code: data.postal_code ?? '',
          country: data.country || DEFAULT_COUNTRY,
        },
        vat_id: data.vat_id,
      })
      toast.success('Billing address saved')
    } catch {
      // Error already handled by mutation
    } finally {
      setSavingAddress(false)
    }
  })

  const updateAddress = (field: keyof BillingAddressFormData, value: string) => {
    const previousCountry = currentAddress.country
    addressForm.setValue(field, value, { shouldValidate: true })

    // When country changes, update VAT prefix if EU country
    if (field === 'country') {
      const updatedVatId = updateVatIdForCountryChange(currentVatId, previousCountry, value)
      addressForm.setValue('vat_id', updatedVatId, { shouldValidate: true })
    }
  }

  // Handle address selection from Google Places autocomplete
  const handleAddressSelect = useCallback(
    (parsed: ParsedAddress) => {
      const previousCountry = currentAddress.country
      const countryCode = parsed.country_code.toUpperCase()

      // Update address fields from parsed Google Places result
      addressForm.setValue('line1', parsed.street_address || parsed.formatted_address, {
        shouldValidate: true,
      })
      addressForm.setValue('line2', '', { shouldValidate: true })
      addressForm.setValue('city', parsed.city, { shouldValidate: true })
      addressForm.setValue('state', parsed.state, { shouldValidate: true })
      addressForm.setValue('postal_code', parsed.postal_code, { shouldValidate: true })
      addressForm.setValue('country', countryCode, { shouldValidate: true })

      // Trigger VAT prefix update for the new country
      const updatedVatId = updateVatIdForCountryChange(currentVatId, previousCountry, countryCode)
      addressForm.setValue('vat_id', updatedVatId, { shouldValidate: true })
    },
    [currentAddress.country, currentVatId, addressForm.setValue]
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
                    deliveryForm.setValue('use_billing_email', isChecked)
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
                        deliveryForm.reset({
                          use_billing_email: false,
                          billing_email: '',
                        })
                      } catch {
                        // Revert on failure
                        deliveryForm.setValue('use_billing_email', true)
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
                      {...deliveryForm.register('billing_email')}
                      id="billingEmail"
                      type="email"
                      className="w-full max-w-sm px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      placeholder="billing@company.com"
                    />
                    {deliveryForm.formState.errors.billing_email && (
                      <p className="text-xs text-destructive mt-1">
                        {deliveryForm.formState.errors.billing_email.message}
                      </p>
                    )}
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
                  {...addressForm.register('billing_name')}
                  id="billingName"
                  type="text"
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Acme Corporation Inc."
                />
                {addressForm.formState.errors.billing_name && (
                  <p className="text-xs text-destructive mt-1">
                    {addressForm.formState.errors.billing_name.message}
                  </p>
                )}
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
                  {...addressForm.register('line2')}
                  id="line2"
                  type="text"
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Apt, Suite, Floor (optional)"
                />
                {addressForm.formState.errors.line2 && (
                  <p className="text-xs text-destructive mt-1">
                    {addressForm.formState.errors.line2.message}
                  </p>
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label htmlFor="city" className="block text-sm font-medium mb-1">
                    City
                  </label>
                  <input
                    {...addressForm.register('city')}
                    id="city"
                    type="text"
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  {addressForm.formState.errors.city && (
                    <p className="text-xs text-destructive mt-1">
                      {addressForm.formState.errors.city.message}
                    </p>
                  )}
                </div>

                <div>
                  <label htmlFor="state" className="block text-sm font-medium mb-1">
                    {getStateLabel(currentAddress.country)}
                  </label>
                  <input
                    {...addressForm.register('state')}
                    id="state"
                    type="text"
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  {addressForm.formState.errors.state && (
                    <p className="text-xs text-destructive mt-1">
                      {addressForm.formState.errors.state.message}
                    </p>
                  )}
                </div>

                <div>
                  <label htmlFor="postalCode" className="block text-sm font-medium mb-1">
                    {getPostalCodeLabel(currentAddress.country)}
                  </label>
                  <input
                    {...addressForm.register('postal_code')}
                    id="postalCode"
                    type="text"
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  {addressForm.formState.errors.postal_code && (
                    <p className="text-xs text-destructive mt-1">
                      {addressForm.formState.errors.postal_code.message}
                    </p>
                  )}
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
                            addressForm.setValue('vat_id', currentVatPrefix + e.target.value, {
                              shouldValidate: true,
                            })
                          }}
                          className="flex-1 px-3 py-2 border border-border rounded-r-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          placeholder="123456789"
                        />
                      </div>
                    ) : (
                      <input
                        {...addressForm.register('vat_id')}
                        id="vatId"
                        type="text"
                        className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        placeholder="Enter VAT ID"
                      />
                    )}
                    {addressForm.formState.errors.vat_id && (
                      <p className="text-xs text-destructive mt-1">
                        {addressForm.formState.errors.vat_id.message}
                      </p>
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
