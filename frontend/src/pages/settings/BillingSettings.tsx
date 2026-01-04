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
import { useApi } from "../../hooks/useApi"
import type { BillingAddress, Invoice, SubscriptionInfo } from "../../lib/api"
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
  const {
    getOrganization,
    updateBilling,
    getSubscription,
    createPortalSession,
    listInvoices,
  } = useApi()
  const billingEmailRef = useRef<HTMLInputElement>(null)
  const [useBillingEmail, setUseBillingEmail] = useState(false)
  const [billingEmail, setBillingEmail] = useState("")
  const [billingName, setBillingName] = useState("")
  const [address, setAddress] = useState<BillingAddress>({
    line1: "",
    line2: "",
    city: "",
    state: "",
    postal_code: "",
    country: "",
  })
  const [vatId, setVatId] = useState("")
  const [loading, setLoading] = useState(true)
  const [savingDelivery, setSavingDelivery] = useState(false)
  const [savingAddress, setSavingAddress] = useState(false)

  // Subscription state
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(
    null
  )
  const [showUpgradeForm, setShowUpgradeForm] = useState(false)
  const [loadingPortal, setLoadingPortal] = useState(false)

  // Invoice state
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [invoicesLoading, setInvoicesLoading] = useState(false)
  const [invoicesHasMore, setInvoicesHasMore] = useState(false)
  const [loadingMoreInvoices, setLoadingMoreInvoices] = useState(false)

  // Focus billing email input when checkbox is enabled
  useEffect(() => {
    if (useBillingEmail) {
      billingEmailRef.current?.focus()
    }
  }, [useBillingEmail])

  useEffect(() => {
    void Promise.all([getOrganization(), getSubscription()])
      .then(([orgData, subData]) => {
        setUseBillingEmail(orgData.billing.use_billing_email)
        setBillingEmail(orgData.billing.billing_email)
        setBillingName(orgData.billing.billing_name)
        // Default country to US if not set
        const country = orgData.billing.address.country || DEFAULT_COUNTRY
        setAddress({ ...orgData.billing.address, country })
        setVatId(orgData.billing.vat_id)
        setSubscription(subData)
      })
      .finally(() => { setLoading(false); })
  }, [getOrganization, getSubscription])

  // Fetch invoices when subscription is active
  useEffect(() => {
    if (subscription && subscription.status !== "none") {
      setInvoicesLoading(true)
      listInvoices({ limit: 6 })
        .then((data) => {
          setInvoices(data.invoices)
          setInvoicesHasMore(data.has_more)
        })
        .catch((err: unknown) => {
          console.error("Failed to load invoices:", err)
        })
        .finally(() => { setInvoicesLoading(false); })
    }
  }, [subscription, listInvoices])

  const loadMoreInvoices = async () => {
    if (!invoices.length || loadingMoreInvoices) return
    setLoadingMoreInvoices(true)
    try {
      const lastInvoice = invoices[invoices.length - 1]
      const data = await listInvoices({
        limit: 6,
        starting_after: lastInvoice.id,
      })
      setInvoices((prev) => [...prev, ...data.invoices])
      setInvoicesHasMore(data.has_more)
    } catch {
      toast.error("Failed to load more invoices")
    } finally {
      setLoadingMoreInvoices(false)
    }
  }

  const handleUpgradeSuccess = async () => {
    setShowUpgradeForm(false)
    // Refetch subscription status
    // PaymentForm has already synced the subscription via confirmSubscription
    try {
      const subData = await getSubscription()
      setSubscription(subData)
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to refresh subscription"
      )
      // Reload page as fallback
      window.location.reload()
    }
  }

  const handleManageSubscription = async () => {
    setLoadingPortal(true)
    try {
      const { portal_url } = await createPortalSession({
        return_url: `${window.location.origin}/settings/billing`,
      })
      window.location.href = portal_url
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to open billing portal"
      )
      setLoadingPortal(false)
    }
  }

  const saveBillingInfo = async (
    setLoading: (v: boolean) => void,
    successMessage: string
  ) => {
    setLoading(true)
    try {
      await updateBilling({
        use_billing_email: useBillingEmail,
        billing_email: useBillingEmail ? billingEmail : undefined,
        billing_name: billingName,
        address,
        vat_id: vatId,
      })
      toast.success(successMessage)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update")
    } finally {
      setLoading(false)
    }
  }

  const handleDeliverySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveBillingInfo(setSavingDelivery, "Invoice delivery settings saved")
  }

  const handleAddressSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveBillingInfo(setSavingAddress, "Billing address saved")
  }

  const updateAddress = (field: keyof BillingAddress, value: string) => {
    const previousCountry = address.country
    setAddress((prev) => ({ ...prev, [field]: value }))

    // When country changes, update VAT prefix if EU country
    if (field === "country") {
      setVatId((currentVat) =>
        updateVatIdForCountryChange(currentVat, previousCountry, value)
      )
    }
  }

  // Handle address selection from Google Places autocomplete
  const handleAddressSelect = useCallback(
    (parsed: ParsedAddress) => {
      const previousCountry = address.country
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
        updateVatIdForCountryChange(currentVat, previousCountry, countryCode)
      )
    },
    [address.country]
  )

  // Get current VAT prefix based on country
  const currentVatPrefix = getVatPrefix(address.country)

  // Format date for display
  const formatDate = (isoDate: string | null) => {
    if (!isoDate) return null
    return new Date(isoDate).toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    })
  }

  if (loading) {
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
                  onCancel={() => { setShowUpgradeForm(false); }}
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
                            ? `Cancels ${formatDate(subscription.current_period_end)}`
                            : `Renews ${formatDate(subscription.current_period_end)}`}
                        </>
                      )}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={handleManageSubscription}
                    disabled={loadingPortal}
                  >
                    {loadingPortal ? "Loading..." : "Manage Subscription"}
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
                <Button onClick={() => { setShowUpgradeForm(true); }}>
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
                  checked={useBillingEmail}
                  onCheckedChange={async (checked) => {
                    const isChecked = checked === true
                    const previousValue = useBillingEmail
                    setUseBillingEmail(isChecked)
                    if (!isChecked) {
                      // Auto-save when unchecking since the form is hidden
                      setSavingDelivery(true)
                      try {
                        await updateBilling({
                          use_billing_email: false,
                          billing_name: billingName,
                          address,
                          vat_id: vatId,
                        })
                        toast.success("Invoice delivery settings saved")
                      } catch (err) {
                        toast.error(
                          err instanceof Error
                            ? err.message
                            : "Failed to update"
                        )
                        setUseBillingEmail(previousValue) // Revert to original state on failure
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

              {useBillingEmail && (
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
                      value={billingEmail}
                      onChange={(e) => { setBillingEmail(e.target.value); }}
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
                  value={billingName}
                  onChange={(e) => { setBillingName(e.target.value); }}
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
                  value={address.line1}
                  onChange={(value) => { updateAddress("line1", value); }}
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
                  value={address.line2}
                  onChange={(e) => { updateAddress("line2", e.target.value); }}
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
                    value={address.city}
                    onChange={(e) => { updateAddress("city", e.target.value); }}
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                <div>
                  <label
                    htmlFor="state"
                    className="block text-sm font-medium mb-1"
                  >
                    {getStateLabel(address.country)}
                  </label>
                  <input
                    id="state"
                    type="text"
                    value={address.state}
                    onChange={(e) => { updateAddress("state", e.target.value); }}
                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                <div>
                  <label
                    htmlFor="postalCode"
                    className="block text-sm font-medium mb-1"
                  >
                    {getPostalCodeLabel(address.country)}
                  </label>
                  <input
                    id="postalCode"
                    type="text"
                    value={address.postal_code}
                    onChange={(e) => { updateAddress("postal_code", e.target.value); }
                    }
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
                    value={address.country}
                    onValueChange={(value) => { updateAddress("country", value); }}
                    placeholder="Select country..."
                  />
                </div>

                {shouldShowTaxId(address.country) && (
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
                            vatId.startsWith(currentVatPrefix)
                              ? vatId.slice(currentVatPrefix.length)
                              : vatId
                          }
                          onChange={(e) => { setVatId(currentVatPrefix + e.target.value); }
                          }
                          className="flex-1 px-3 py-2 border border-border rounded-r-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          placeholder="123456789"
                        />
                      </div>
                    ) : (
                      <input
                        id="vatId"
                        type="text"
                        value={vatId}
                        onChange={(e) => { setVatId(e.target.value); }}
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
              ) : invoices.length === 0 ? (
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
                        {invoices.map((invoice) => (
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
