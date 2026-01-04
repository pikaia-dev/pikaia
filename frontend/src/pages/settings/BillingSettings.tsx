import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { PaymentForm } from "../../components/PaymentForm"
import { AddressAutocomplete } from "../../components/ui/address-autocomplete"
import { Button } from "../../components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card"
import { Checkbox } from "../../components/ui/checkbox"
import { CountryCombobox } from "../../components/ui/country-combobox"
import { LoadingSpinner } from "../../components/ui/loading-spinner"
import {
  useCreatePortalSession,
  useInvoices,
  useRefreshSubscription,
  useSubscription,
} from "../../features/billing/queries"
import {
  useOrganization,
  useUpdateBilling,
} from "../../features/organization/queries"
import type { BillingAddress, Invoice } from "../../lib/api"
import {
  DEFAULT_COUNTRY,
  getPostalCodeLabel,
  getStateLabel,
  getVatPrefix,
  shouldShowTaxId,
  updateVatIdForCountryChange,
} from "../../lib/countries"
import type { ParsedAddress } from "../../lib/google-places"

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
  const createPortalMutation = useCreatePortalSession()
  const refreshSubscription = useRefreshSubscription()

  // Form state (editable fields)
  const [useBillingEmail, setUseBillingEmail] = useState<boolean | null>(null)
  const [billingEmail, setBillingEmail] = useState<string | null>(null)
  const [billingName, setBillingName] = useState<string | null>(null)
  const [address, setAddress] = useState<BillingAddress | null>(null)
  const [vatId, setVatId] = useState<string | null>(null)
  const [savingDelivery, setSavingDelivery] = useState(false)
  const [savingAddress, setSavingAddress] = useState(false)

  // UI state
  const [showUpgradeForm, setShowUpgradeForm] = useState(false)

  // Invoice pagination state (additional invoices beyond first page)
  const [additionalInvoices, setAdditionalInvoices] = useState<Invoice[]>([])
  const [invoicesHasMore, setInvoicesHasMore] = useState(false)
  const [loadingMoreInvoices, setLoadingMoreInvoices] = useState(false)

  // Derived values from server data or edited values
  const currentUseBillingEmail =
    useBillingEmail ?? organization?.billing.use_billing_email ?? false
  const currentBillingEmail =
    billingEmail ?? organization?.billing.billing_email ?? ""
  const currentBillingName =
    billingName ?? organization?.billing.billing_name ?? ""
  const currentAddress = address ?? {
    line1: organization?.billing.address.line1 ?? "",
    line2: organization?.billing.address.line2 ?? "",
    city: organization?.billing.address.city ?? "",
    state: organization?.billing.address.state ?? "",
    postal_code: organization?.billing.address.postal_code ?? "",
    country: organization?.billing.address.country || DEFAULT_COUNTRY,
  }
  const currentVatId = vatId ?? organization?.billing.vat_id ?? ""

  // Update invoices pagination state when data changes
  useEffect(() => {
    if (invoicesData) {
      setInvoicesHasMore(invoicesData.has_more)
    }
  }, [invoicesData])

  // Combine base invoices with additional loaded invoices
  const allInvoices = [
    ...(invoicesData?.invoices ?? []),
    ...additionalInvoices,
  ]

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
      const response = await fetch(
        `/api/v1/billing/invoices?limit=6&starting_after=${lastInvoice.id}`,
        {
          headers: {
            Authorization: `Bearer ${getSessionToken()}`,
          },
        }
      )
      if (!response.ok) throw new Error("Failed to load more invoices")
      const data = (await response.json()) as {
        invoices: Invoice[]
        has_more: boolean
      }
      setAdditionalInvoices((prev) => [...prev, ...data.invoices])
      setInvoicesHasMore(data.has_more)
    } catch {
      toast.error("Failed to load more invoices")
    } finally {
      setLoadingMoreInvoices(false)
    }
  }

  // Helper to get session token - we need this for additional invoice fetching
  const getSessionToken = (): string => {
    // Access the Stytch session from local storage or session storage
    const session = localStorage.getItem("stytch_session_jwt")
    return session ?? ""
  }

  const handleUpgradeSuccess = () => {
    setShowUpgradeForm(false)
    refreshSubscription()
  }

  const handleManageSubscription = () => {
    createPortalMutation.mutate(
      { return_url: `${window.location.origin}/settings/billing` },
      {
        onSuccess: (data) => {
          window.location.href = data.portal_url
        },
      }
    )
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
      toast.success("Invoice delivery settings saved")
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
      toast.success("Billing address saved")
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
    if (field === "country") {
      setVatId((currentVat) =>
        updateVatIdForCountryChange(
          currentVat ?? currentVatId,
          previousCountry,
          value
        )
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
        line2: "", // User can fill manually if needed
        city: parsed.city,
        state: parsed.state,
        postal_code: parsed.postal_code,
        country: parsed.country_code.toUpperCase(),
      })

      // Trigger VAT prefix update for the new country
      const countryCode = parsed.country_code.toUpperCase()
      setVatId((currentVat) =>
        updateVatIdForCountryChange(
          currentVat ?? currentVatId,
          previousCountry,
          countryCode
        )
      )
    },
    [currentAddress.country, currentVatId]
  )

  // Get current VAT prefix based on country
  const currentVatPrefix = getVatPrefix(currentAddress.country)

  // Format date for display
  const formatDate = (isoDate: string | null) => {
    if (!isoDate) return null
    return new Date(isoDate).toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    })
  }

  const isLoading = orgLoading || subLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  const isSubscribed = subscription && subscription.status !== "none"
  const memberCount = subscription?.quantity || 1

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Billing</h1>
        <p className="text-muted-foreground">
          Manage billing information for invoices
        </p>
      </div>

      <div className="space-y-6 max-w-2xl">
        {/* Subscription Status Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Subscription</CardTitle>
            <CardDescription>
              {isSubscribed
                ? "Manage your subscription and billing"
                : "Upgrade to unlock all features"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {showUpgradeForm ? (
              <div className="space-y-4">
                <div className="border-b pb-4 mb-4">
                  <h3 className="font-medium">Subscribe to Pro Plan</h3>
                  <p className="text-sm text-muted-foreground">
                    ${10 * memberCount}/month for {memberCount}{" "}
                    {memberCount === 1 ? "seat" : "seats"}
                  </p>
                </div>
                <PaymentForm
                  quantity={memberCount}
                  onSuccess={handleUpgradeSuccess}
                  onCancel={() => {
                    setShowUpgradeForm(false)
                  }}
                />
              </div>
            ) : isSubscribed ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Pro Plan</span>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${subscription.status === "active"
                          ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                          : subscription.status === "past_due"
                            ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
                            : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                          }`}
                      >
                        {subscription.status === "active"
                          ? "Active"
                          : subscription.status === "past_due"
                            ? "Past Due"
                            : subscription.status === "trialing"
                              ? "Trial"
                              : subscription.status}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {subscription.quantity}{" "}
                      {subscription.quantity === 1 ? "seat" : "seats"}
                      {subscription.current_period_end && (
                        <>
                          {" · "}
                          {subscription.cancel_at_period_end
                            ? `Cancels ${formatDate(subscription.current_period_end) ?? ""}`
                            : `Renews ${formatDate(subscription.current_period_end) ?? ""}`}
                        </>
                      )}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={handleManageSubscription}
                    disabled={createPortalMutation.isPending}
                  >
                    {createPortalMutation.isPending
                      ? "Loading..."
                      : "Manage Subscription"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Free Plan</p>
                  <p className="text-sm text-muted-foreground">
                    {memberCount} {memberCount === 1 ? "member" : "members"}
                  </p>
                </div>
                <Button
                  onClick={() => {
                    setShowUpgradeForm(true)
                  }}
                >
                  Upgrade to Pro
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Invoice Delivery Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Invoice Delivery</CardTitle>
            <CardDescription>
              Choose where to receive your invoices
            </CardDescription>
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
                        toast.success("Invoice delivery settings saved")
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
                    <label
                      htmlFor="billingEmail"
                      className="block text-sm font-medium mb-1"
                    >
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
                      {savingDelivery ? "Saving..." : "Save"}
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
              <CardDescription>
                This information will appear on your invoices
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label
                  htmlFor="billingName"
                  className="block text-sm font-medium mb-1"
                >
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
                <label
                  htmlFor="line1"
                  className="block text-sm font-medium mb-1"
                >
                  Street Address
                </label>
                <AddressAutocomplete
                  id="line1"
                  value={currentAddress.line1}
                  onChange={(value) => {
                    updateAddress("line1", value)
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
                <label
                  htmlFor="line2"
                  className="block text-sm font-medium mb-1"
                >
                  Address Line 2
                </label>
                <input
                  id="line2"
                  type="text"
                  value={currentAddress.line2}
                  onChange={(e) => {
                    updateAddress("line2", e.target.value)
                  }}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Apt, Suite, Floor (optional)"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label
                    htmlFor="city"
                    className="block text-sm font-medium mb-1"
                  >
                    City
                  </label>
                  <input
                    id="city"
                    type="text"
                    value={currentAddress.city}
                    onChange={(e) => {
                      updateAddress("city", e.target.value)
                    }}
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                <div>
                  <label
                    htmlFor="state"
                    className="block text-sm font-medium mb-1"
                  >
                    {getStateLabel(currentAddress.country)}
                  </label>
                  <input
                    id="state"
                    type="text"
                    value={currentAddress.state}
                    onChange={(e) => {
                      updateAddress("state", e.target.value)
                    }}
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                <div>
                  <label
                    htmlFor="postalCode"
                    className="block text-sm font-medium mb-1"
                  >
                    {getPostalCodeLabel(currentAddress.country)}
                  </label>
                  <input
                    id="postalCode"
                    type="text"
                    value={currentAddress.postal_code}
                    onChange={(e) => {
                      updateAddress("postal_code", e.target.value)
                    }}
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="country"
                    className="block text-sm font-medium mb-1"
                  >
                    Country
                  </label>
                  <CountryCombobox
                    value={currentAddress.country}
                    onValueChange={(value) => {
                      updateAddress("country", value)
                    }}
                    placeholder="Select country..."
                  />
                </div>

                {shouldShowTaxId(currentAddress.country) && (
                  <div>
                    <label
                      htmlFor="vatId"
                      className="block text-sm font-medium mb-1"
                    >
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
                      {currentVatPrefix
                        ? "EU VAT number for tax exemption"
                        : "VAT ID (optional)"}
                    </p>
                  </div>
                )}
              </div>

              <Button type="submit" disabled={savingAddress}>
                {savingAddress ? "Saving..." : "Save billing info"}
              </Button>
            </CardContent>
          </form>
        </Card>

        {/* Invoice History Card - show only when subscribed */}
        {isSubscribed && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Invoice History</CardTitle>
              <CardDescription>
                View and download your past invoices
              </CardDescription>
            </CardHeader>
            <CardContent>
              {invoicesLoading ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="sm" />
                </div>
              ) : allInvoices.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">
                  No invoices yet. Your first invoice will appear here after
                  your subscription renews.
                </p>
              ) : (
                <div className="space-y-4">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 font-medium">
                            Invoice
                          </th>
                          <th className="text-left py-2 font-medium">Status</th>
                          <th className="text-right py-2 font-medium">
                            Amount
                          </th>
                          <th className="text-right py-2 font-medium">Date</th>
                          <th className="text-right py-2 font-medium sr-only">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {allInvoices.map((invoice) => (
                          <tr
                            key={invoice.id}
                            className="border-b last:border-0"
                          >
                            <td className="py-3">
                              <span className="font-mono text-xs">
                                {invoice.number || invoice.id.slice(-8)}
                              </span>
                            </td>
                            <td className="py-3">
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${invoice.status === "paid"
                                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                  : invoice.status === "open"
                                    ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
                                    : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                                  }`}
                              >
                                {invoice.status.charAt(0).toUpperCase() +
                                  invoice.status.slice(1)}
                              </span>
                            </td>
                            <td className="py-3 text-right">
                              {new Intl.NumberFormat(undefined, {
                                style: "currency",
                                currency: invoice.currency.toUpperCase(),
                              }).format(invoice.amount_paid / 100)}
                            </td>
                            <td className="py-3 text-right text-muted-foreground">
                              {formatDate(invoice.created)}
                            </td>
                            <td className="py-3 text-right">
                              <div className="flex items-center justify-end gap-2">
                                {invoice.hosted_invoice_url && (
                                  <a
                                    href={invoice.hosted_invoice_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-primary hover:underline"
                                  >
                                    View
                                  </a>
                                )}
                                {invoice.invoice_pdf && (
                                  <a
                                    href={invoice.invoice_pdf}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-primary hover:underline"
                                  >
                                    PDF
                                  </a>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {invoicesHasMore && (
                    <div className="flex justify-center pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={loadMoreInvoices}
                        disabled={loadingMoreInvoices}
                      >
                        {loadingMoreInvoices ? "Loading..." : "Load more"}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
