import { useStytchB2BClient, useStytchMember } from '@stytch/react/b2b'
import {
  Building2,
  ChevronsUpDown,
  CreditCard,
  Home,
  LogOut,
  Settings,
  Shield,
  User,
  Users,
  Webhook,
} from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
} from '@/components/ui/sidebar'
import { useCurrentUser } from '@/features/auth/queries'
import { STYTCH_ROLES } from '@/lib/constants'

const mainNavItems = [{ to: '/dashboard', label: 'Dashboard', icon: Home }]

// Organization-level settings (admin-only)
const organizationNavItems = [
  { to: '/settings/organization', label: 'General', icon: Building2 },
  { to: '/settings/members', label: 'Members', icon: Users },
  { to: '/settings/billing', label: 'Billing', icon: CreditCard },
  { to: '/settings/security', label: 'Security', icon: Shield },
  { to: '/settings/integrations', label: 'Integrations', icon: Webhook },
]

export function AppSidebar() {
  const stytch = useStytchB2BClient()
  const { member } = useStytchMember()
  const navigate = useNavigate()
  const { data: userData } = useCurrentUser()

  // Get avatar from React Query cache (auto-updates when cache changes)
  const avatarUrl = userData?.user.avatar_url || null

  // Check admin from Stytch roles
  const roles = member?.roles || []
  const isAdmin = roles.some((r: { role_id?: string }) => r.role_id === STYTCH_ROLES.ADMIN)

  const handleLogout = async () => {
    try {
      await stytch.session.revoke()
      // eslint-disable-next-line @typescript-eslint/no-floating-promises -- navigate returns void
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

        {/* Organization Settings - admin only */}
        {isAdmin && (
          <SidebarGroup>
            <SidebarGroupLabel>Organization</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {organizationNavItems.map((item) => (
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
        )}
      </SidebarContent>

      <SidebarFooter className="p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="w-full data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  {avatarUrl ? (
                    <img
                      src={avatarUrl}
                      alt="Avatar"
                      className="h-8 w-8 rounded-full object-cover shrink-0"
                    />
                  ) : (
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-accent text-sidebar-accent-foreground text-sm font-medium shrink-0">
                      {/* eslint-disable @typescript-eslint/no-unnecessary-condition -- member properties can be undefined */}
                      {member?.name?.[0]?.toUpperCase() ||
                        member?.email_address?.[0]?.toUpperCase() ||
                        '?'}
                      {/* eslint-enable @typescript-eslint/no-unnecessary-condition */}
                    </div>
                  )}
                  <div className="flex flex-1 flex-col text-left text-sm min-w-0">
                    <span className="font-medium truncate">{member?.name || 'User'}</span>
                    <span className="text-xs text-sidebar-foreground/70 truncate">
                      {member?.email_address}
                    </span>
                  </div>
                  <ChevronsUpDown className="ml-auto h-4 w-4 opacity-50" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56"
                side="top"
                align="start"
                sideOffset={4}
              >
                <DropdownMenuItem asChild>
                  <NavLink to="/settings/profile" className="cursor-pointer">
                    <User className="h-4 w-4" />
                    <span>Profile</span>
                  </NavLink>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
                  <LogOut className="h-4 w-4" />
                  <span>Log out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
