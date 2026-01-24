import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { queryKeys } from '@/api/query-keys'
import type { InitiateLinkResponse } from '@/api/types'
import { useApi } from '@/api/use-api'

export function useInitiateDeviceLink() {
  const { initiateDeviceLink } = useApi()

  return useMutation<InitiateLinkResponse, Error>({
    mutationFn: initiateDeviceLink,
  })
}

export function useRevokeDevice() {
  const { revokeDevice } = useApi()
  const queryClient = useQueryClient()

  return useMutation<void, Error, number>({
    mutationFn: revokeDevice,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.devices.all })
      toast.success('Device removed')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to remove device')
    },
  })
}
