import { Users } from 'lucide-react'
import { useState } from 'react'
import type { DirectoryUser } from '@/api/types'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { SettingsPageLayout } from '@/components/settings-page-layout'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmailAutocomplete } from '@/components/ui/email-autocomplete'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useBulkInviteMembers,
  useDeleteMember,
  useInviteMember,
  useUpdateMemberRole,
} from '@/features/members/api/mutations'
import { useMembers } from '@/features/members/api/queries'
import { BulkInviteDialog } from '@/features/members/components/bulk-invite-dialog'
import { MembersTable } from '@/features/members/components/members-table'
import { useConfirmDialog } from '@/hooks/use-confirm-dialog'

export default function MembersSettings() {
  const { data: membersData, isLoading, error } = useMembers()
  const inviteMutation = useInviteMember()
  const bulkInviteMutation = useBulkInviteMembers()
  const updateRoleMutation = useUpdateMemberRole()
  const deleteMutation = useDeleteMember()

  // Invite form state
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteName, setInviteName] = useState('')
  const [inviteRole, setInviteRole] = useState<'admin' | 'member'>('member')

  // Bulk invite dialog state
  const [bulkInviteOpen, setBulkInviteOpen] = useState(false)

  // Delete confirmation dialog
  const deleteDialog = useConfirmDialog<{ id: number; email: string }>((member) => {
    deleteMutation.mutate(member.id, {
      onSettled: () => deleteDialog.reset(),
    })
  })

  const members = membersData?.members ?? []

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteEmail) return

    inviteMutation.mutate(
      { email: inviteEmail, name: inviteName, role: inviteRole },
      {
        onSuccess: () => {
          setInviteEmail('')
          setInviteName('')
          setInviteRole('member')
        },
      }
    )
  }

  // Handle directory user selection
  const handleDirectoryUserSelect = (user: DirectoryUser) => {
    setInviteEmail(user.email)
    if (user.name) {
      setInviteName(user.name)
    }
  }

  // Handle bulk invite
  const handleBulkInvite = (
    members: { email: string; name: string; phone: string; role: string }[]
  ) => {
    bulkInviteMutation.mutate(
      {
        members: members.map((m) => ({
          email: m.email,
          name: m.name || undefined,
          phone: m.phone || undefined,
          role: m.role as 'admin' | 'member',
        })),
      },
      {
        onSuccess: () => {
          setBulkInviteOpen(false)
        },
      }
    )
  }

  const handleRoleChange = (memberId: number, newRole: 'admin' | 'member') => {
    updateRoleMutation.mutate({ memberId, role: newRole })
  }

  const openDeleteDialog = (memberId: number, email: string) => {
    deleteDialog.openDialog({ id: memberId, email })
  }

  return (
    <SettingsPageLayout
      title="Members"
      description="Manage your organization members"
      maxWidth=""
      isLoading={isLoading}
      error={error}
    >
      {/* Invite Form */}
      <Card className="mb-6">
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle className="text-base">Invite Member</CardTitle>
            <CardDescription>Send an invitation email to add a new member</CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setBulkInviteOpen(true)
            }}
          >
            <Users className="h-4 w-4 mr-2" />
            Bulk Invite
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleInvite} className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label htmlFor="email" className="block text-sm font-medium mb-1">
                Email
              </label>
              <EmailAutocomplete
                id="email"
                value={inviteEmail}
                onChange={setInviteEmail}
                onSelect={handleDirectoryUserSelect}
                placeholder="user@example.com"
              />
            </div>
            <div className="w-40">
              <label htmlFor="name" className="block text-sm font-medium mb-1">
                Name (optional)
              </label>
              <input
                id="name"
                type="text"
                value={inviteName}
                onChange={(e) => {
                  setInviteName(e.target.value)
                }}
                placeholder="Jane Doe"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="w-32">
              <label htmlFor="role" className="block text-sm font-medium mb-1">
                Role
              </label>
              <Select
                value={inviteRole}
                onValueChange={(value) => {
                  setInviteRole(value as 'admin' | 'member')
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={inviteMutation.isPending || !inviteEmail}>
              {inviteMutation.isPending ? 'Sending...' : 'Send Invite'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Members Table */}
      <MembersTable members={members} onRoleChange={handleRoleChange} onRemove={openDeleteDialog} />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialog.open}
        onOpenChange={deleteDialog.onOpenChange}
        onConfirm={deleteDialog.onConfirm}
        title="Remove member"
        description={
          <>
            Are you sure you want to remove <strong>{deleteDialog.item?.email}</strong> from this
            organization? They will lose access immediately.
          </>
        }
        confirmLabel="Remove"
        variant="destructive"
      />

      {/* Bulk Invite Dialog */}
      <BulkInviteDialog
        open={bulkInviteOpen}
        onOpenChange={setBulkInviteOpen}
        onInvite={handleBulkInvite}
        isLoading={bulkInviteMutation.isPending}
      />
    </SettingsPageLayout>
  )
}
