import type { MemberListItem } from '@/api/types'
import { StatusBadge } from '@/components/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface MembersTableProps {
  members: MemberListItem[]
  onRoleChange: (memberId: number, newRole: 'admin' | 'member') => void
  onRemove: (memberId: number, email: string) => void
}

/**
 * Table component for displaying organization members.
 */
export function MembersTable({ members, onRoleChange, onRemove }: MembersTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Organization Members</CardTitle>
        <CardDescription>
          {members.length} active member{members.length !== 1 ? 's' : ''}
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
                  className={`border-t ${member.status === 'invited' ? 'opacity-60' : ''}`}
                >
                  <td className="p-3">{member.email}</td>
                  <td className="p-3 text-muted-foreground">{member.name || '—'}</td>
                  <td className="p-3">
                    {member.status === 'invited' ? (
                      <StatusBadge variant="warning">Pending</StatusBadge>
                    ) : (
                      <StatusBadge variant="success">Active</StatusBadge>
                    )}
                  </td>
                  <td className="p-3">
                    <Select
                      value={member.role}
                      onValueChange={(value) => {
                        onRoleChange(member.id, value as 'admin' | 'member')
                      }}
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
                      onClick={() => {
                        onRemove(member.id, member.email)
                      }}
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
  )
}
