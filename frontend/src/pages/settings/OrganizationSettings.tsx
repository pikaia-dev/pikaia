import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { useApi } from '../../hooks/useApi'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { LoadingSpinner } from '../../components/ui/loading-spinner'
import { ImageUploader } from '../../components/ui/image-uploader'

export default function OrganizationSettings() {
    const { getOrganization, updateOrganization } = useApi()
    const [name, setName] = useState('')
    const [slug, setSlug] = useState('')
    const [logoUrl, setLogoUrl] = useState('')
    const [slugManuallyEdited, setSlugManuallyEdited] = useState(false)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

    /**
     * Normalize a slug to meet Stytch requirements.
     * Must match backend normalize_slug() in apps/accounts/schemas.py
     * 
     * Allowed characters: a-z, 0-9, hyphen, period, underscore, tilde
     */
    const normalizeSlug = (value: string): string => {
        return value
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9._~-]+/g, '-')  // Replace non-allowed chars with hyphen
            .replace(/^-+|-+$/g, '')           // Remove leading/trailing hyphens
            .slice(0, 128)                     // Truncate to max length
    }

    useEffect(() => {
        getOrganization()
            .then((data) => {
                setName(data.name)
                setSlug(data.slug)
                setLogoUrl(data.logo_url || '')
            })
            .finally(() => setLoading(false))
    }, [getOrganization])

    const handleNameChange = (newName: string) => {
        setName(newName)
        // Auto-update slug if user hasn't manually edited it
        if (!slugManuallyEdited) {
            setSlug(normalizeSlug(newName))
        }
    }

    const handleSlugChange = (newSlug: string) => {
        const normalized = normalizeSlug(newSlug)
        setSlug(normalized)
        // Mark as manually edited if different from auto-derived
        if (normalized !== normalizeSlug(name)) {
            setSlugManuallyEdited(true)
        }
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setSaving(true)

        try {
            await updateOrganization({ name, slug })
            toast.success('Organization updated successfully')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to update')
        } finally {
            setSaving(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner size="sm" />
            </div>
        )
    }

    return (
        <div className="p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-semibold">Organization</h1>
                <p className="text-muted-foreground">Manage your organization settings</p>
            </div>

            <div className="space-y-6 max-w-lg">
                {/* Logo Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Organization Logo</CardTitle>
                        <CardDescription>Upload a logo for your organization</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <ImageUploader
                            type="logo"
                            value={logoUrl}
                            onChange={setLogoUrl}
                        />
                    </CardContent>
                </Card>

                {/* Organization Details Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Organization Details</CardTitle>
                        <CardDescription>Update your organization information</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label htmlFor="name" className="block text-sm font-medium mb-1">
                                    Organization name
                                </label>
                                <input
                                    id="name"
                                    type="text"
                                    value={name}
                                    onChange={(e) => handleNameChange(e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="Your organization name"
                                />
                            </div>

                            <div>
                                <label htmlFor="slug" className="block text-sm font-medium mb-1">
                                    Slug
                                </label>
                                <input
                                    id="slug"
                                    type="text"
                                    value={slug}
                                    onChange={(e) => handleSlugChange(e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="your-organization"
                                />
                                <p className="text-xs text-muted-foreground mt-1">
                                    URL-friendly identifier (lowercase, hyphens, 2-128 chars)
                                </p>
                            </div>

                            <Button type="submit" disabled={saving}>
                                {saving ? 'Saving...' : 'Save changes'}
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
