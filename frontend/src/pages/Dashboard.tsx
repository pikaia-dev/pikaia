import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStytchB2BClient, useStytchMemberSession, useStytchMember } from '@stytch/react/b2b'
import { getCurrentUser, type MeResponse } from '../lib/api'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'

export default function Dashboard() {
    const stytch = useStytchB2BClient()
    const { session } = useStytchMemberSession()
    const { member } = useStytchMember()
    const navigate = useNavigate()
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
    }, [session])

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
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900"></div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <Card className="w-full max-w-md">
                    <CardHeader>
                        <CardTitle className="text-red-600">Error</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-slate-600 mb-4">{error}</p>
                        <Button onClick={handleLogout} variant="outline">
                            Back to Login
                        </Button>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <header className="bg-white border-b border-slate-200">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center h-16">
                        <div className="flex items-center space-x-4">
                            <h1 className="text-xl font-semibold text-slate-900">
                                {userData?.organization.name || 'Dashboard'}
                            </h1>
                            {userData?.organization.slug && (
                                <span className="text-sm text-slate-500 bg-slate-100 px-2 py-1 rounded">
                                    {userData.organization.slug}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center space-x-4">
                            <span className="text-sm text-slate-600">
                                {userData?.user.email || member?.email_address}
                            </span>
                            <Button onClick={handleLogout} variant="outline" size="sm">
                                Logout
                            </Button>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {/* User Info Card */}
                    <Card>
                        <CardHeader>
                            <CardTitle>User</CardTitle>
                            <CardDescription>Your account details</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div>
                                <span className="text-sm text-slate-500">Name</span>
                                <p className="font-medium">{userData?.user.name || 'Not set'}</p>
                            </div>
                            <div>
                                <span className="text-sm text-slate-500">Email</span>
                                <p className="font-medium">{userData?.user.email}</p>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Member Info Card */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Membership</CardTitle>
                            <CardDescription>Your role in this organization</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div>
                                <span className="text-sm text-slate-500">Role</span>
                                <p className="font-medium capitalize">{userData?.member.role}</p>
                            </div>
                            <div>
                                <span className="text-sm text-slate-500">Admin</span>
                                <p className="font-medium">{userData?.member.is_admin ? 'Yes' : 'No'}</p>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Organization Info Card */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Organization</CardTitle>
                            <CardDescription>Current workspace</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div>
                                <span className="text-sm text-slate-500">Name</span>
                                <p className="font-medium">{userData?.organization.name}</p>
                            </div>
                            <div>
                                <span className="text-sm text-slate-500">Slug</span>
                                <p className="font-medium">{userData?.organization.slug}</p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </main>
        </div>
    )
}
