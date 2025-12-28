import { useState, useEffect } from 'react'
import { useApi } from '../../hooks/useApi'
import type { BillingAddress } from '../../lib/api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'

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
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

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
        setMessage(null)

        try {
            await updateBilling({
                billing_email: billingEmail || undefined,
                billing_name: billingName,
                address,
                vat_id: vatId,
            })
            setMessage({ type: 'success', text: 'Billing info updated successfully' })
        } catch (err) {
            setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to update' })
        } finally {
            setSaving(false)
        }
    }

    const updateAddress = (field: keyof BillingAddress, value: string) => {
        setAddress((prev) => ({ ...prev, [field]: value }))
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-foreground" />
            </div>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Billing</CardTitle>
                <CardDescription>Manage billing information for invoices</CardDescription>
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
                                Country code
                            </label>
                            <input
                                id="country"
                                type="text"
                                value={address.country}
                                onChange={(e) => updateAddress('country', e.target.value.toUpperCase().slice(0, 2))}
                                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                placeholder="US"
                                maxLength={2}
                            />
                            <p className="text-xs text-muted-foreground mt-1">ISO 3166-1 alpha-2 (e.g., US, DE, PL)</p>
                        </div>

                        <div>
                            <label htmlFor="vatId" className="block text-sm font-medium mb-1">
                                VAT ID
                            </label>
                            <input
                                id="vatId"
                                type="text"
                                value={vatId}
                                onChange={(e) => setVatId(e.target.value)}
                                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                placeholder="DE123456789"
                            />
                            <p className="text-xs text-muted-foreground mt-1">EU VAT number for tax exemption</p>
                        </div>
                    </div>

                    {message && (
                        <p className={`text-sm ${message.type === 'success' ? 'text-green-600' : 'text-destructive'}`}>
                            {message.text}
                        </p>
                    )}

                    <Button type="submit" disabled={saving}>
                        {saving ? 'Saving...' : 'Save billing info'}
                    </Button>
                </form>
            </CardContent>
        </Card>
    )
}
