import type { DiscoveredOrganization } from "@stytch/vanilla-js/b2b"
import { BuildingIcon, ChevronRightIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { LoadingSpinner } from "@/components/ui/loading-spinner"

interface OrganizationSelectorProps {
    organizations: DiscoveredOrganization[]
    onSelect: (organizationId: string) => void
    onBack: () => void
    isLoading: boolean
    error: string | null
    email: string
}

function getMembershipLabel(type: string): string | null {
    switch (type) {
        case "pending_member":
            return "Join"
        case "invited_member":
            return "Accept Invite"
        default:
            return null
    }
}

export function OrganizationSelector({
    organizations,
    onSelect,
    onBack,
    isLoading,
    error,
    email,
}: OrganizationSelectorProps) {
    if (organizations.length === 0) {
        return (
            <div className="text-center space-y-6">
                <div className="space-y-2">
                    <h2 className="text-xl font-semibold">Unable to create organization</h2>
                    <p className="text-sm text-muted-foreground">
                        <span className="font-medium text-foreground">{email}</span> encountered
                        an issue during setup.
                    </p>
                </div>

                <p className="text-xs text-muted-foreground">
                    Please try again or contact support if this issue persists.
                </p>

                <Button variant="ghost" onClick={onBack} className="text-sm">
                    Try a different email
                </Button>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="text-center space-y-2">
                <h2 className="text-xl font-semibold">Select an organization</h2>
                <p className="text-sm text-muted-foreground">
                    Choose which organization to sign in to
                </p>
            </div>

            {error && (
                <p className="text-xs text-destructive text-center">{error}</p>
            )}

            <div className="space-y-2">
                {organizations.map((discoveredOrg) => {
                    const org = discoveredOrg.organization
                    const membershipLabel = getMembershipLabel(
                        discoveredOrg.membership.type
                    )

                    return (
                        <button
                            key={org.organization_id}
                            type="button"
                            onClick={() => {
                                onSelect(org.organization_id)
                            }}
                            disabled={isLoading}
                            className="w-full flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent transition-colors text-left disabled:opacity-50"
                        >
                            <div className="flex items-center gap-3">
                                {org.organization_logo_url ? (
                                    <img
                                        src={org.organization_logo_url}
                                        alt=""
                                        className="h-8 w-8 rounded object-cover"
                                    />
                                ) : (
                                    <div className="h-8 w-8 rounded bg-muted flex items-center justify-center">
                                        <BuildingIcon className="h-4 w-4 text-muted-foreground" />
                                    </div>
                                )}
                                <span className="font-medium text-sm">
                                    {org.organization_name}
                                </span>
                            </div>

                            <div className="flex items-center gap-2">
                                {membershipLabel && (
                                    <span className="text-xs text-muted-foreground">
                                        {membershipLabel}
                                    </span>
                                )}
                                {isLoading ? (
                                    <LoadingSpinner size="sm" />
                                ) : (
                                    <ChevronRightIcon className="h-4 w-4 text-muted-foreground" />
                                )}
                            </div>
                        </button>
                    )
                })}
            </div>

            <div className="text-center">
                <Button variant="ghost" onClick={onBack} className="text-sm">
                    Use a different email
                </Button>
            </div>
        </div>
    )
}
