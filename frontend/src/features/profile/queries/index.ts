import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { useApi } from '../../../hooks/useApi'
import type { UserInfo } from '../../../lib/api'
import { queryKeys } from '../../shared/query-keys'

/**
 * Mutation hook for updating user profile.
 */
export function useUpdateProfile() {
  const { updateProfile } = useApi()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: { name: string }) => updateProfile(data),
    onSuccess: (updatedUser: UserInfo) => {
      // Update the user data in the auth.me cache
      queryClient.setQueryData(queryKeys.auth.me(), (old: unknown) => {
        if (old && typeof old === 'object' && 'user' in old) {
          return { ...old, user: updatedUser }
        }
        return old
      })
      toast.success('Profile updated')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update profile')
    },
  })
}

/**
 * Mutation hook for sending phone OTP.
 */
export function useSendPhoneOtp() {
  const { sendPhoneOtp } = useApi()

  return useMutation({
    mutationFn: (phone_number: string) => sendPhoneOtp(phone_number),
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to send verification code')
    },
  })
}

/**
 * Mutation hook for verifying phone OTP.
 */
export function useVerifyPhoneOtp() {
  const { verifyPhoneOtp } = useApi()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ phone_number, otp_code }: { phone_number: string; otp_code: string }) =>
      verifyPhoneOtp(phone_number, otp_code),
    onSuccess: (updatedUser: UserInfo) => {
      // Update the user data in the auth.me cache
      queryClient.setQueryData(queryKeys.auth.me(), (old: unknown) => {
        if (old && typeof old === 'object' && 'user' in old) {
          return { ...old, user: updatedUser }
        }
        return old
      })
      toast.success('Phone number verified')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to verify code')
    },
  })
}

/**
 * Mutation hook for starting email update.
 */
export function useStartEmailUpdate() {
  const { startEmailUpdate } = useApi()

  return useMutation({
    mutationFn: (new_email: string) => startEmailUpdate(new_email),
    onSuccess: () => {
      toast.success('Verification email sent')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to send verification email')
    },
  })
}
