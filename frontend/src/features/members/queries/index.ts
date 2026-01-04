import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { useApi } from "../../../hooks/useApi"
import type {
    InviteMemberRequest,
    InviteMemberResponse,
    MemberListResponse,
    MessageResponse,
} from "../../../lib/api"
import { queryKeys } from "../../shared/query-keys"

/**
 * Query hook for fetching organization members.
 */
export function useMembers() {
    const { listMembers } = useApi()

    return useQuery<MemberListResponse>({
        queryKey: queryKeys.members.list(),
        queryFn: listMembers,
    })
}

/**
 * Mutation hook for inviting a new member.
 */
export function useInviteMember() {
    const { inviteMember } = useApi()
    const queryClient = useQueryClient()

    return useMutation<InviteMemberResponse, Error, InviteMemberRequest>({
        mutationFn: inviteMember,
        onSuccess: () => {
            // Invalidate to refetch the members list
            void queryClient.invalidateQueries({ queryKey: queryKeys.members.all })
            toast.success("Invitation sent")
        },
        onError: (error) => {
            toast.error(error.message || "Failed to invite member")
        },
    })
}

/**
 * Mutation hook for updating a member's role.
 */
export function useUpdateMemberRole() {
    const { updateMemberRole } = useApi()
    const queryClient = useQueryClient()

    return useMutation<
        MessageResponse,
        Error,
        { memberId: number; role: "admin" | "member" }
    >({
        mutationFn: ({ memberId, role }) => updateMemberRole(memberId, { role }),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: queryKeys.members.all })
            toast.success("Role updated")
        },
        onError: (error) => {
            toast.error(error.message || "Failed to update role")
        },
    })
}

/**
 * Mutation hook for deleting a member.
 */
export function useDeleteMember() {
    const { deleteMember } = useApi()
    const queryClient = useQueryClient()

    return useMutation<MessageResponse, Error, number>({
        mutationFn: deleteMember,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: queryKeys.members.all })
            toast.success("Member removed")
        },
        onError: (error) => {
            toast.error(error.message || "Failed to remove member")
        },
    })
}
