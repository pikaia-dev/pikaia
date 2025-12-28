import { useState, useEffect } from 'react'
import { useApi } from '../../hooks/useApi'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'

export default function OrganizationSettings() {
    const { getOrganization, updateOrganization } = useApi()
    const [name, setName] = useState('')
    const [slug, setSlug] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

    useEffect(() => {
        getOrganization()
            .then((data) => {
                setName(data.name)
                setSlug(data.slug)
            })
            .finally(() => setLoading(false))
    }, [getOrganization])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setSaving(true)
        setMessage(null)

        try {
            await updateOrganization({ name })
            setMessage({ type: 'success', text: 'Organization updated successfully' })
        } catch (err) {
            setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to update' })
        } finally {
            setSaving(false)
        }
    }

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
                <h1 className="text-2xl font-semibold">Organization</h1>
                <p className="text-muted-foreground">Manage your organization settings</p>
            </div>

            <Card className="max-w-lg">
                <CardHeader>
                    <CardTitle className="text-base">Organization Details</CardTitle>
                    <CardDescription>Update your organization information</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label htmlFor="slug" className="block text-sm font-medium mb-1">
                                Slug
                            </label>
                            <input
                                id="slug"
                                type="text"
                                value={slug}
                                disabled
                                className="w-full px-3 py-2 border border-border rounded-md bg-muted text-muted-foreground text-sm"
                            />
                            <p className="text-xs text-muted-foreground mt-1">
                                Organization slug is managed by Stytch and cannot be changed
                            </p>
                        </div>

                        <div>
                            <label htmlFor="name" className="block text-sm font-medium mb-1">
                                Organization name
                            </label>
                            <input
                                id="name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                placeholder="Your organization name"
                            />
                        </div>

                        {message && (
                            <p className={`text-sm ${message.type === 'success' ? 'text-green-600' : 'text-destructive'}`}>
                                {message.text}
                            </p>
                        )}

                        <Button type="submit" disabled={saving}>
                            {saving ? 'Saving...' : 'Save changes'}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    )
}
