import { NavLink, useNavigate } from 'react-router-dom'
import { useStytchB2BClient, useStytchMember } from '@stytch/react/b2b'
import { Home, User, Users, Building2, CreditCard, LogOut, Settings } from 'lucide-react'
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupContent,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    SidebarSeparator,
} from './ui/sidebar'

const mainNavItems = [
    { to: '/dashboard', label: 'Dashboard', icon: Home },
]

const settingsNavItems = [
    { to: '/settings/profile', label: 'Profile', icon: User },
    { to: '/settings/organization', label: 'Organization', icon: Building2, adminOnly: true },
    { to: '/settings/members', label: 'Members', icon: Users, adminOnly: true },
    { to: '/settings/billing', label: 'Billing', icon: CreditCard, adminOnly: true },
]

export function AppSidebar() {
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
        <Sidebar>
            <SidebarHeader className="border-b border-sidebar-border">
                <div className="flex items-center gap-2 px-2 py-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
                        <Settings className="h-4 w-4" />
                    </div>
                    <span className="font-semibold">Your App</span>
                </div>
            </SidebarHeader>

            <SidebarContent>
                {/* Main Navigation */}
                <SidebarGroup>
                    <SidebarGroupLabel>Application</SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            {mainNavItems.map((item) => (
                                <SidebarMenuItem key={item.to}>
                                    <SidebarMenuButton asChild>
                                        <NavLink
                                            to={item.to}
                                            className={({ isActive }) =>
                                                isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''
                                            }
                                        >
                                            <item.icon className="h-4 w-4" />
                                            <span>{item.label}</span>
                                        </NavLink>
                                    </SidebarMenuButton>
                                </SidebarMenuItem>
                            ))}
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>

                <SidebarSeparator />

                {/* Settings Navigation */}
                <SidebarGroup>
                    <SidebarGroupLabel>Settings</SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            {settingsNavItems
                                .filter((item) => !item.adminOnly || isAdmin)
                                .map((item) => (
                                    <SidebarMenuItem key={item.to}>
                                        <SidebarMenuButton asChild>
                                            <NavLink
                                                to={item.to}
                                                className={({ isActive }) =>
                                                    isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''
                                                }
                                            >
                                                <item.icon className="h-4 w-4" />
                                                <span>{item.label}</span>
                                            </NavLink>
                                        </SidebarMenuButton>
                                    </SidebarMenuItem>
                                ))}
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>
            </SidebarContent>

            <SidebarFooter className="border-t border-sidebar-border">
                <SidebarMenu>
                    <SidebarMenuItem>
                        <SidebarMenuButton asChild>
                            <div className="flex items-center gap-2">
                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-accent text-sidebar-accent-foreground text-sm font-medium">
                                    {member?.name?.[0]?.toUpperCase() || member?.email_address?.[0]?.toUpperCase() || '?'}
                                </div>
                                <div className="flex flex-1 flex-col text-left text-sm">
                                    <span className="font-medium truncate">
                                        {member?.name || 'User'}
                                    </span>
                                    <span className="text-xs text-sidebar-foreground/70 truncate">
                                        {member?.email_address}
                                    </span>
                                </div>
                            </div>
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                    <SidebarMenuItem>
                        <SidebarMenuButton onClick={handleLogout}>
                            <LogOut className="h-4 w-4" />
                            <span>Log out</span>
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarFooter>
        </Sidebar>
    )
}
