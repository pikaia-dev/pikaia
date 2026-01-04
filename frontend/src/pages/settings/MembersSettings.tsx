import { useCallback,useEffect, useState } from "react"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../components/ui/alert-dialog"
import { Button } from "../../components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card"
import { EmailAutocomplete } from "../../components/ui/email-autocomplete"
import { LoadingSpinner } from "../../components/ui/loading-spinner"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select"
import { useApi } from "../../hooks/useApi"
import type { DirectoryUser,MemberListItem } from "../../lib/api"

export default function MembersSettings() {
  const { listMembers, inviteMember, updateMemberRole, deleteMember } = useApi()
  const [members, setMembers] = useState<MemberListItem[]>([])
  const [loading, setLoading] = useState(true)

  // Invite form state
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteName, setInviteName] = useState("")
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member")
  const [inviting, setInviting] = useState(false)

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [memberToDelete, setMemberToDelete] = useState<{
    id: number
    email: string
  } | null>(null)

  const loadMembers = useCallback(async () => {
    try {
      const data = await listMembers()
      setMembers(data.members)
    } catch (err) {
      // Use toast ID to prevent duplicates from React StrictMode
      toast.error(
        err instanceof Error ? err.message : "Failed to load members",
        {
          id: "load-members-error",
        }
      )
    } finally {
      setLoading(false)
    }
  }, [listMembers])

  useEffect(() => {
    loadMembers()
  }, [loadMembers])

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteEmail) return

    setInviting(true)

    try {
      const response = await inviteMember({
        email: inviteEmail,
        name: inviteName,
        role: inviteRole,
      })
      toast.success(response.message)
      setInviteEmail("")
      setInviteName("")
      setInviteRole("member")
      loadMembers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send invite")
    } finally {
      setInviting(false)
    }
  }

  // Handle directory user selection
  const handleDirectoryUserSelect = (user: DirectoryUser) => {
    setInviteEmail(user.email)
    if (user.name) {
      setInviteName(user.name)
    }
  }

  const handleRoleChange = async (
    memberId: number,
    newRole: "admin" | "member"
  ) => {
    try {
      await updateMemberRole(memberId, { role: newRole })
      toast.success("Role updated")
      loadMembers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update role")
    }
  }

  const openDeleteDialog = (memberId: number, email: string) => {
    setMemberToDelete({ id: memberId, email })
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!memberToDelete) return

    try {
      await deleteMember(memberToDelete.id)
      toast.success(`${memberToDelete.email} removed`)
      loadMembers()
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to remove member"
      )
    } finally {
      setDeleteDialogOpen(false)
      setMemberToDelete(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Members</h1>
        <p className="text-muted-foreground">
          Manage your organization members
        </p>
      </div>

      {/* Invite Form */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Invite Member</CardTitle>
          <CardDescription>
            Send an invitation email to add a new member
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleInvite}
            className="flex flex-wrap gap-3 items-end"
          >
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
                onChange={(e) => setInviteName(e.target.value)}
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
                onValueChange={(value) =>
                  setInviteRole(value as "admin" | "member")
                }
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
            <Button type="submit" disabled={inviting || !inviteEmail}>
              {inviting ? "Sending..." : "Send Invite"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Members List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Organization Members</CardTitle>
          <CardDescription>
            {members.length} active member{members.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-3 font-medium">Email</th>
                  <th className="text-left p-3 font-medium">Name</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-left p-3 font-medium">Role</th>
                  <th className="text-right p-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr
                    key={member.id}
                    className={`border-t ${member.status === "invited" ? "opacity-60" : ""}`}
                  >
                    <td className="p-3">{member.email}</td>
                    <td className="p-3 text-muted-foreground">
                      {member.name || "—"}
                    </td>
                    <td className="p-3">
                      {member.status === "invited" ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                          Pending
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                          Active
                        </span>
                      )}
                    </td>
                    <td className="p-3">
                      <Select
                        value={member.role}
                        onValueChange={(value) =>
                          handleRoleChange(
                            member.id,
                            value as "admin" | "member"
                          )
                        }
                      >
                        <SelectTrigger className="w-28 h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="member">Member</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="p-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          openDeleteDialog(member.id, member.email)
                        }
                        className="text-destructive hover:text-destructive"
                      >
                        Remove
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove member</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove{" "}
              <strong>{memberToDelete?.email}</strong> from this organization?
              They will lose access immediately.
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
    </div>
  )
}
