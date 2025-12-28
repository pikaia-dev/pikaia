import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStytchB2BClient, useStytchMemberSession, useStytchMember } from '@stytch/react/b2b'
import { useApi } from '../hooks/useApi'
import type { MeResponse } from '../lib/api'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'

export default function Dashboard() {
    const stytch = useStytchB2BClient()
    const { session } = useStytchMemberSession()
    const { member } = useStytchMember()
    const navigate = useNavigate()
    const { getCurrentUser } = useApi()
    const [userData, setUserData] = useState<MeResponse | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        async function fetchUser() {
            try {
                const data = await getCurrentUser()
                setUserData(data)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load user data')
            } finally {
                setLoading(false)
            }
        }

        if (session) {
            fetchUser()
        }
    }, [session, getCurrentUser])

    const handleLogout = async () => {
        try {
            await stytch.session.revoke()
            navigate('/login', { replace: true })
        } catch (err) {
            console.error('Logout error:', err)
        }
    }

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground"></div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Card className="w-full max-w-md">
                    <CardHeader>
                        <CardTitle className="text-destructive">Error</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-muted-foreground mb-4">{error}</p>
                        <Button onClick={handleLogout} variant="outline">
                            Back to Login
                        </Button>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-background">
            <header className="bg-card border-b border-border">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center h-14">
                        <div className="flex items-center gap-3">
                            <h1 className="text-lg font-semibold">
                                {userData?.organization.name || 'Dashboard'}
                            </h1>
                            {userData?.organization.slug && (
                                <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                                    {userData.organization.slug}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-4">
                            <span className="text-sm text-muted-foreground">
                                {userData?.user.email || member?.email_address}
                            </span>
                            <Button onClick={handleLogout} variant="outline" size="sm">
                                Log out
                            </Button>
                        </div>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">User</CardTitle>
                            <CardDescription>Your account details</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div>
                                <span className="text-xs text-muted-foreground">Name</span>
                                <p className="text-sm font-medium">{userData?.user.name || 'Not set'}</p>
                            </div>
                            <div>
                                <span className="text-xs text-muted-foreground">Email</span>
                                <p className="text-sm font-medium">{userData?.user.email}</p>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Membership</CardTitle>
                            <CardDescription>Your role in this organization</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div>
                                <span className="text-xs text-muted-foreground">Role</span>
                                <p className="text-sm font-medium capitalize">{userData?.member.role}</p>
                            </div>
                            <div>
                                <span className="text-xs text-muted-foreground">Admin</span>
                                <p className="text-sm font-medium">{userData?.member.is_admin ? 'Yes' : 'No'}</p>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Organization</CardTitle>
                            <CardDescription>Current workspace</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div>
                                <span className="text-xs text-muted-foreground">Name</span>
                                <p className="text-sm font-medium">{userData?.organization.name}</p>
                            </div>
                            <div>
                                <span className="text-xs text-muted-foreground">Slug</span>
                                <p className="text-sm font-medium">{userData?.organization.slug}</p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </main>
        </div>
    )
}

