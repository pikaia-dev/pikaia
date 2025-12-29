import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { useApi } from '../../hooks/useApi'
import type { BillingAddress } from '../../lib/api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { CountryCombobox } from '../../components/ui/country-combobox'
import { getVatPrefix } from '../../lib/countries'

export default function BillingSettings() {
    const { getOrganization, updateBilling } = useApi()
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
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        getOrganization()
            .then((data) => {
                setBillingEmail(data.billing.billing_email)
                setBillingName(data.billing.billing_name)
                setAddress(data.billing.address)
                setVatId(data.billing.vat_id)
            })
            .finally(() => setLoading(false))
    }, [getOrganization])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setSaving(true)

        try {
            await updateBilling({
                billing_email: billingEmail || undefined,
                billing_name: billingName,
                address,
                vat_id: vatId,
            })
            toast.success('Billing info updated successfully')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to update')
        } finally {
            setSaving(false)
        }
    }

    const updateAddress = (field: keyof BillingAddress, value: string) => {
        setAddress((prev) => ({ ...prev, [field]: value }))

        // When country changes, update VAT prefix if EU country
        if (field === 'country') {
            const prefix = getVatPrefix(value)
            if (prefix) {
                // Only update if VAT is empty or starts with a different prefix
                setVatId((currentVat) => {
                    // If VAT is empty or doesn't have a valid prefix, set the new one
                    if (!currentVat || !currentVat.match(/^[A-Z]{2,3}/)) {
                        return prefix
                    }
                    // If VAT already has a prefix, replace it
                    const vatWithoutPrefix = currentVat.replace(/^[A-Z]{2,3}/, '')
                    return prefix + vatWithoutPrefix
                })
            }
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

            <Card className="max-w-2xl">
                <CardHeader>
                    <CardTitle className="text-base">Billing Information</CardTitle>
                    <CardDescription>This information will appear on your invoices</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid gap-4 sm:grid-cols-2">
                            <div>
                                <label htmlFor="billingEmail" className="block text-sm font-medium mb-1">
                                    Billing email
                                </label>
                                <input
                                    id="billingEmail"
                                    type="email"
                                    value={billingEmail}
                                    onChange={(e) => setBillingEmail(e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="billing@company.com"
                                />
                            </div>

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

                        <Button type="submit" disabled={saving}>
                            {saving ? 'Saving...' : 'Save billing info'}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    )
}
