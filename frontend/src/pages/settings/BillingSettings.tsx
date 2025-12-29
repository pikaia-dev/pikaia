import { useState, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { useApi } from '../../hooks/useApi'
import type { BillingAddress } from '../../lib/api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { Checkbox } from '../../components/ui/checkbox'
import { CountryCombobox } from '../../components/ui/country-combobox'
import { getVatPrefix } from '../../lib/countries'

/**
 * Matches EU VAT ID country prefixes (2-3 uppercase letters at the start).
 * Examples: "DE" (Germany), "FR" (France), "EL" (Greece), "ATU" (Austria - legacy)
 */
const VAT_PREFIX_PATTERN = /^[A-Z]{2,3}/

export default function BillingSettings() {
    const { getOrganization, updateBilling } = useApi()
    const billingEmailRef = useRef<HTMLInputElement>(null)
    const [useBillingEmail, setUseBillingEmail] = useState(false)
    const [billingEmail, setBillingEmail] = useState('')
    const [billingName, setBillingName] = useState('')
    const [address, setAddress] = useState<BillingAddress>({
        line1: '',
        line2: '',
        city: '',
        state: '',
        postal_code: '',
        country: '',
    })
    const [vatId, setVatId] = useState('')
    const [loading, setLoading] = useState(true)
    const [savingDelivery, setSavingDelivery] = useState(false)
    const [savingAddress, setSavingAddress] = useState(false)

    useEffect(() => {
        getOrganization()
            .then((data) => {
                setUseBillingEmail(data.billing.use_billing_email)
                setBillingEmail(data.billing.billing_email)
                setBillingName(data.billing.billing_name)
                setAddress(data.billing.address)
                setVatId(data.billing.vat_id)
            })
            .finally(() => setLoading(false))
    }, [getOrganization])

    const handleDeliverySubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setSavingDelivery(true)

        try {
            await updateBilling({
                use_billing_email: useBillingEmail,
                billing_email: useBillingEmail ? billingEmail : undefined,
                billing_name: billingName,
                address,
                vat_id: vatId,
            })
            toast.success('Invoice delivery settings saved')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to update')
        } finally {
            setSavingDelivery(false)
        }
    }

    const handleAddressSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setSavingAddress(true)

        try {
            await updateBilling({
                use_billing_email: useBillingEmail,
                billing_email: useBillingEmail ? billingEmail : undefined,
                billing_name: billingName,
                address,
                vat_id: vatId,
            })
            toast.success('Billing address saved')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to update')
        } finally {
            setSavingAddress(false)
        }
    }

    const updateAddress = (field: keyof BillingAddress, value: string) => {
        setAddress((prev) => ({ ...prev, [field]: value }))

        // When country changes, update VAT prefix if EU country
        if (field === 'country') {
            const newPrefix = getVatPrefix(value)
            const oldPrefix = getVatPrefix(address.country)

            setVatId((currentVat) => {
                if (newPrefix) {
                    // Switching to EU country - add/replace prefix
                    if (!currentVat || !currentVat.match(VAT_PREFIX_PATTERN)) {
                        return newPrefix
                    }
                    // Replace old prefix with new one
                    const vatWithoutPrefix = currentVat.replace(VAT_PREFIX_PATTERN, '')
                    return newPrefix + vatWithoutPrefix
                } else if (oldPrefix && currentVat) {
                    // Switching from EU to non-EU - remove the old prefix
                    return currentVat.replace(new RegExp(`^${oldPrefix}`), '')
                }
                return currentVat
            })
        }
    }

    // Get current VAT prefix based on country
    const currentVatPrefix = getVatPrefix(address.country)

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-foreground" />
            </div>
        )
    }

    return (
        <div className="p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-semibold">Billing</h1>
                <p className="text-muted-foreground">Manage billing information for invoices</p>
            </div>

            <div className="space-y-6 max-w-2xl">
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
                                    checked={useBillingEmail}
                                    onCheckedChange={(checked) => {
                                        const isChecked = checked === true
                                        setUseBillingEmail(isChecked)
                                        if (isChecked) {
                                            setTimeout(() => billingEmailRef.current?.focus(), 0)
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
                                        <label htmlFor="billingEmail" className="block text-sm font-medium mb-1">
                                            Billing email
                                        </label>
                                        <input
                                            ref={billingEmailRef}
                                            id="billingEmail"
                                            type="email"
                                            value={billingEmail}
                                            onChange={(e) => setBillingEmail(e.target.value)}
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
                                    value={billingName}
                                    onChange={(e) => setBillingName(e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="Acme Corporation Inc."
                                />
                            </div>

                            <div>
                                <label htmlFor="line1" className="block text-sm font-medium mb-1">
                                    Address line 1
                                </label>
                                <input
                                    id="line1"
                                    type="text"
                                    value={address.line1}
                                    onChange={(e) => updateAddress('line1', e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="123 Main Street"
                                />
                            </div>

                            <div>
                                <label htmlFor="line2" className="block text-sm font-medium mb-1">
                                    Address line 2
                                </label>
                                <input
                                    id="line2"
                                    type="text"
                                    value={address.line2}
                                    onChange={(e) => updateAddress('line2', e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="Suite 100"
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
                                        value={address.city}
                                        onChange={(e) => updateAddress('city', e.target.value)}
                                        className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    />
                                </div>

                                <div>
                                    <label htmlFor="state" className="block text-sm font-medium mb-1">
                                        State / Province
                                    </label>
                                    <input
                                        id="state"
                                        type="text"
                                        value={address.state}
                                        onChange={(e) => updateAddress('state', e.target.value)}
                                        className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    />
                                </div>

                                <div>
                                    <label htmlFor="postalCode" className="block text-sm font-medium mb-1">
                                        Postal code
                                    </label>
                                    <input
                                        id="postalCode"
                                        type="text"
                                        value={address.postal_code}
                                        onChange={(e) => updateAddress('postal_code', e.target.value)}
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
                                        value={address.country}
                                        onValueChange={(value) => updateAddress('country', value)}
                                        placeholder="Select country..."
                                    />
                                </div>

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
                                                value={vatId.replace(new RegExp(`^${currentVatPrefix}`), '')}
                                                onChange={(e) => setVatId(currentVatPrefix + e.target.value)}
                                                className="flex-1 px-3 py-2 border border-border rounded-r-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                                placeholder="123456789"
                                            />
                                        </div>
                                    ) : (
                                        <input
                                            id="vatId"
                                            type="text"
                                            value={vatId}
                                            onChange={(e) => setVatId(e.target.value)}
                                            className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                            placeholder="Enter VAT ID"
                                        />
                                    )}
                                    <p className="text-xs text-muted-foreground mt-1">
                                        {currentVatPrefix ? 'EU VAT number for tax exemption' : 'VAT ID (optional)'}
                                    </p>
                                </div>
                            </div>

                            <Button type="submit" disabled={savingAddress}>
                                {savingAddress ? 'Saving...' : 'Save billing info'}
                            </Button>
                        </CardContent>
                    </form>
                </Card>
            </div>
        </div>
    )
}
