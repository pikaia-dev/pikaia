import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { useApi } from '../../hooks/useApi'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { LoadingSpinner } from '../../components/ui/loading-spinner'
import { ImageUploader } from '../../components/ui/image-uploader'

export default function ProfileSettings() {
    const { getCurrentUser, updateProfile } = useApi()
    const [name, setName] = useState('')
    const [email, setEmail] = useState('')
    const [avatarUrl, setAvatarUrl] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        getCurrentUser()
            .then((data) => {
                setName(data.user.name)
                setEmail(data.user.email)
                setAvatarUrl(data.user.avatar_url || '')
            })
            .catch((err) => {
                toast.error(err instanceof Error ? err.message : 'Failed to load profile')
            })
            .finally(() => setLoading(false))
    }, [getCurrentUser])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setSaving(true)

        try {
            await updateProfile({ name })
            toast.success('Profile updated successfully')
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
                <h1 className="text-2xl font-semibold">Profile</h1>
                <p className="text-muted-foreground">Manage your personal information</p>
            </div>

            <div className="space-y-6 max-w-lg">
                {/* Avatar Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Profile Picture</CardTitle>
                        <CardDescription>Upload a photo to personalize your account</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <ImageUploader
                            type="avatar"
                            value={avatarUrl}
                            onChange={setAvatarUrl}
                        />
                    </CardContent>
                </Card>

                {/* Personal Details Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Personal Details</CardTitle>
                        <CardDescription>Update your profile information</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label htmlFor="email" className="block text-sm font-medium mb-1">
                                    Email
                                </label>
                                <input
                                    id="email"
                                    type="email"
                                    value={email}
                                    disabled
                                    className="w-full px-3 py-2 border border-border rounded-md bg-muted text-muted-foreground text-sm"
                                />
                                <p className="text-xs text-muted-foreground mt-1">
                                    Email is managed by Stytch and cannot be changed here
                                </p>
                            </div>

                            <div>
                                <label htmlFor="name" className="block text-sm font-medium mb-1">
                                    Display name
                                </label>
                                <input
                                    id="name"
                                    type="text"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="Your name"
                                />
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
