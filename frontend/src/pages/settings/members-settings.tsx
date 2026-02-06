import { zodResolver } from '@hookform/resolvers/zod'
import { Users } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import type { DirectoryUser } from '@/api/types'
import { SettingsPageLayout } from '@/components/settings-page-layout'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
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
import type { InviteMemberFormData } from '@/features/members/forms/schema'
import { inviteMemberSchema } from '@/features/members/forms/schema'

export default function MembersSettings() {
  const { data: membersData, isLoading, error } = useMembers()
  const inviteMutation = useInviteMember()
  const bulkInviteMutation = useBulkInviteMembers()
  const updateRoleMutation = useUpdateMemberRole()
  const deleteMutation = useDeleteMember()

  // Invite form (useForm + zodResolver)
  const inviteForm = useForm<InviteMemberFormData>({
    resolver: zodResolver(inviteMemberSchema),
    defaultValues: {
      email: '',
      name: '',
      role: 'member',
    },
  })

  // Bulk invite dialog state
  const [bulkInviteOpen, setBulkInviteOpen] = useState(false)

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [memberToDelete, setMemberToDelete] = useState<{
    id: number
    email: string
  } | null>(null)

  const members = membersData?.members ?? []

  const handleInvite = inviteForm.handleSubmit((data) => {
    inviteMutation.mutate(
      { email: data.email, name: data.name, role: data.role },
      {
        onSuccess: () => {
          inviteForm.reset()
        },
      }
    )
  })

  // Handle directory user selection
  const handleDirectoryUserSelect = (user: DirectoryUser) => {
    inviteForm.setValue('email', user.email, { shouldValidate: true })
    if (user.name) {
      inviteForm.setValue('name', user.name, { shouldValidate: true })
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
    setMemberToDelete({ id: memberId, email })
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = () => {
    if (!memberToDelete) return

    deleteMutation.mutate(memberToDelete.id, {
      onSettled: () => {
        setDeleteDialogOpen(false)
        setMemberToDelete(null)
      },
    })
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
                value={inviteForm.watch('email')}
                onChange={(value) => {
                  inviteForm.setValue('email', value, { shouldValidate: true })
                }}
                onSelect={handleDirectoryUserSelect}
                placeholder="user@example.com"
              />
              {inviteForm.formState.errors.email && (
                <p className="text-xs text-destructive mt-1">
                  {inviteForm.formState.errors.email.message}
                </p>
              )}
            </div>
            <div className="w-40">
              <label htmlFor="name" className="block text-sm font-medium mb-1">
                Name (optional)
              </label>
              <input
                {...inviteForm.register('name')}
                id="name"
                type="text"
                placeholder="Jane Doe"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {inviteForm.formState.errors.name && (
                <p className="text-xs text-destructive mt-1">
                  {inviteForm.formState.errors.name.message}
                </p>
              )}
            </div>
            <div className="w-32">
              <label htmlFor="role" className="block text-sm font-medium mb-1">
                Role
              </label>
              <Select
                value={inviteForm.watch('role')}
                onValueChange={(value) => {
                  inviteForm.setValue('role', value as 'admin' | 'member', {
                    shouldValidate: true,
                  })
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
            <Button type="submit" disabled={inviteMutation.isPending || !inviteForm.watch('email')}>
              {inviteMutation.isPending ? 'Sending...' : 'Send Invite'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Members Table */}
      <MembersTable members={members} onRoleChange={handleRoleChange} onRemove={openDeleteDialog} />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove member</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove <strong>{memberToDelete?.email}</strong> from this
              organization? They will lose access immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
