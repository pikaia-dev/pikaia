import { useStytchMemberSession } from '@stytch/react/b2b'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useCurrentUser } from '@/features/auth/api/queries'

export default function Dashboard() {
  const { session } = useStytchMemberSession()
  const { data: userData, isLoading, error } = useCurrentUser()

  if (isLoading || !session) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load user data</p>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back, {userData?.user.name || userData?.user.email}
        </p>
      </div>

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
    </div>
  )
}
