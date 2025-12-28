import { NavLink, Outlet } from 'react-router-dom'
import { useStytchMember } from '@stytch/react/b2b'

const navItems = [
    { to: '/settings/profile', label: 'Profile' },
    { to: '/settings/organization', label: 'Organization', adminOnly: true },
    { to: '/settings/billing', label: 'Billing', adminOnly: true },
]

export default function SettingsLayout() {
    const { member } = useStytchMember()

    // Check if member has admin role based on Stytch roles
    const roles = member?.roles || []
    const isAdmin = roles.some((r: { role_id?: string }) => r.role_id === 'stytch_admin')

    return (
        <div className="min-h-screen bg-background">
            <div className="max-w-4xl mx-auto px-4 py-8">
                <h1 className="text-2xl font-semibold mb-6">Settings</h1>

                <div className="flex gap-8">
                    <nav className="w-48 shrink-0">
                        <ul className="space-y-1">
                            {navItems
                                .filter((item) => !item.adminOnly || isAdmin)
                                .map((item) => (
                                    <li key={item.to}>
                                        <NavLink
                                            to={item.to}
                                            className={({ isActive }) =>
                                                `block px-3 py-2 rounded-md text-sm transition-colors ${isActive
                                                    ? 'bg-muted font-medium'
                                                    : 'text-muted-foreground hover:bg-muted/50'
                                                }`
                                            }
                                        >
                                            {item.label}
                                        </NavLink>
                                    </li>
                                ))}
                        </ul>
                    </nav>

                    <main className="flex-1 min-w-0">
                        <Outlet />
                    </main>
                </div>
            </div>
        </div>
    )
}
