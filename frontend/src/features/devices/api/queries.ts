import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import type { DeviceListResponse } from '@/api/types'
import { useApi } from '@/api/use-api'

export function useDevices() {
  const { listDevices } = useApi()

  return useQuery<DeviceListResponse>({
    queryKey: queryKeys.devices.list(),
    queryFn: listDevices,
  })
}
