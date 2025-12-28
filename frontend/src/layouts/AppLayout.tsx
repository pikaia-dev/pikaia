import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useStytchB2BClient, useStytchMember } from '@stytch/react/b2b'
import { Button } from '../components/ui/button'

const mainNavItems = [
    { to: '/dashboard', label: 'Dashboard', icon: '🏠' },
]

const settingsNavItems = [
    { to: '/settings/profile', label: 'Profile' },
    { to: '/settings/organization', label: 'Organization', adminOnly: true },
    { to: '/settings/billing', label: 'Billing', adminOnly: true },
]

export default function AppLayout() {
    const stytch = useStytchB2BClient()
    const { member } = useStytchMember()
    const navigate = useNavigate()

    // Check admin from Stytch roles
    const roles = member?.roles || []
    const isAdmin = roles.some((r: { role_id?: string }) => r.role_id === 'stytch_admin')

    const handleLogout = async () => {
        try {
            await stytch.session.revoke()
            navigate('/login', { replace: true })
        } catch (err) {
            console.error('Logout error:', err)
        }
    }

    return (
        <div className="min-h-screen flex bg-background">
            {/* Left Sidebar */}
            <aside className="w-56 border-r border-border bg-card flex flex-col">
                {/* Logo / Brand */}
                <div className="h-14 flex items-center px-4 border-b border-border">
                    <span className="font-semibold">Your App</span>
                </div>

                {/* Main Navigation */}
                <nav className="flex-1 p-3">
                    <div className="space-y-1">
                        {mainNavItems.map((item) => (
                            <NavLink
                                key={item.to}
                                to={item.to}
                                className={({ isActive }) =>
                                    `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${isActive
                                        ? 'bg-muted font-medium'
                                        : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                                    }`
                                }
                            >
                                <span>{item.icon}</span>
                                {item.label}
                            </NavLink>
                        ))}
                    </div>

                    {/* Settings Section */}
                    <div className="mt-6">
                        <div className="px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Settings
                        </div>
                        <div className="space-y-1">
                            {settingsNavItems
                                .filter((item) => !item.adminOnly || isAdmin)
                                .map((item) => (
                                    <NavLink
                                        key={item.to}
                                        to={item.to}
                                        className={({ isActive }) =>
                                            `block px-3 py-2 rounded-md text-sm transition-colors ${isActive
                                                ? 'bg-muted font-medium'
                                                : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                                            }`
                                        }
                                    >
                                        {item.label}
                                    </NavLink>
                                ))}
                        </div>
                    </div>
                </nav>

                {/* User Section at Bottom */}
                <div className="p-3 border-t border-border">
                    <div className="flex items-center gap-2 px-2 py-1 mb-2">
                        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm font-medium">
                            {member?.name?.[0]?.toUpperCase() || member?.email_address?.[0]?.toUpperCase() || '?'}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">
                                {member?.name || 'User'}
                            </p>
                            <p className="text-xs text-muted-foreground truncate">
                                {member?.email_address}
                            </p>
                        </div>
                    </div>
                    <Button
                        onClick={handleLogout}
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-muted-foreground"
                    >
                        Log out
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto">
                <Outlet />
            </main>
        </div>
    )
}
