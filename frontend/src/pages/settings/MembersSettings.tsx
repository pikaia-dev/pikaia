import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { useApi } from '../../hooks/useApi'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import type { MemberListItem } from '../../lib/api'

export default function MembersSettings() {
    const { listMembers, inviteMember, updateMemberRole, deleteMember } = useApi()
    const [members, setMembers] = useState<MemberListItem[]>([])
    const [loading, setLoading] = useState(true)

    // Invite form state
    const [inviteEmail, setInviteEmail] = useState('')
    const [inviteName, setInviteName] = useState('')
    const [inviteRole, setInviteRole] = useState<'admin' | 'member'>('member')
    const [inviting, setInviting] = useState(false)

    const loadMembers = useCallback(async () => {
        try {
            const data = await listMembers()
            setMembers(data.members)
        } catch (err) {
            // Use toast ID to prevent duplicates from React StrictMode
            toast.error(err instanceof Error ? err.message : 'Failed to load members', {
                id: 'load-members-error',
            })
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
            const response = await inviteMember({ email: inviteEmail, name: inviteName, role: inviteRole })
            toast.success(response.message)
            setInviteEmail('')
            setInviteName('')
            setInviteRole('member')
            loadMembers()
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to send invite')
        } finally {
            setInviting(false)
        }
    }

    const handleRoleChange = async (memberId: number, newRole: 'admin' | 'member') => {
        try {
            await updateMemberRole(memberId, { role: newRole })
            toast.success('Role updated')
            loadMembers()
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to update role')
        }
    }

    const handleDelete = async (memberId: number, email: string) => {
        if (!confirm(`Remove ${email} from this organization?`)) return

        try {
            await deleteMember(memberId)
            toast.success(`${email} removed`)
            loadMembers()
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to remove member')
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-foreground" />
            </div>
        )
    }

    return (
        <div className="p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-semibold">Members</h1>
                <p className="text-muted-foreground">Manage your organization members</p>
            </div>

            {/* Invite Form */}
            <Card className="mb-6">
                <CardHeader>
                    <CardTitle className="text-base">Invite Member</CardTitle>
                    <CardDescription>Send an invitation email to add a new member</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleInvite} className="flex flex-wrap gap-3 items-end">
                        <div className="flex-1 min-w-[200px]">
                            <label htmlFor="email" className="block text-sm font-medium mb-1">Email</label>
                            <input
                                id="email"
                                type="email"
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                placeholder="user@example.com"
                                required
                                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            />
                        </div>
                        <div className="w-40">
                            <label htmlFor="name" className="block text-sm font-medium mb-1">Name (optional)</label>
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
                            <label htmlFor="role" className="block text-sm font-medium mb-1">Role</label>
                            <select
                                id="role"
                                value={inviteRole}
                                onChange={(e) => setInviteRole(e.target.value as 'admin' | 'member')}
                                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                        <Button type="submit" disabled={inviting || !inviteEmail}>
                            {inviting ? 'Sending...' : 'Send Invite'}
                        </Button>
                    </form>
                </CardContent>
            </Card>

            {/* Members List */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Organization Members</CardTitle>
                    <CardDescription>{members.length} active member{members.length !== 1 ? 's' : ''}</CardDescription>
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
                                        className={`border-t ${member.status === 'invited' ? 'opacity-60' : ''}`}
                                    >
                                        <td className="p-3">{member.email}</td>
                                        <td className="p-3 text-muted-foreground">{member.name || '—'}</td>
                                        <td className="p-3">
                                            {member.status === 'invited' ? (
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
                                            <select
                                                value={member.role}
                                                onChange={(e) => handleRoleChange(member.id, e.target.value as 'admin' | 'member')}
                                                className="px-2 py-1 border border-border rounded text-sm bg-background"
                                            >
                                                <option value="member">Member</option>
                                                <option value="admin">Admin</option>
                                            </select>
                                        </td>
                                        <td className="p-3 text-right">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleDelete(member.id, member.email)}
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
        </div>
    )
}
