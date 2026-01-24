import { MoreHorizontal, Plus, Smartphone } from 'lucide-react'
import { useState } from 'react'

import type { DeviceResponse } from '@/api/types'
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useRevokeDevice } from '@/features/devices/api/mutations'
import { useDevices } from '@/features/devices/api/queries'
import { LinkDeviceDialog } from '@/features/devices/components/link-device-dialog'
import { formatDateShort } from '@/lib/format'

function formatPlatform(platform: string): string {
  const platformMap: Record<string, string> = {
    ios: 'iOS',
    android: 'Android',
  }
  return platformMap[platform.toLowerCase()] ?? platform
}

interface DeviceItemProps {
  device: DeviceResponse
  onRemove: (device: DeviceResponse) => void
}

function DeviceItem({ device, onRemove }: DeviceItemProps) {
  const metadata = [
    device.os_version && `${formatPlatform(device.platform)} ${device.os_version}`,
    device.app_version && `App v${device.app_version}`,
    `Linked ${formatDateShort(device.created_at)}`,
  ]
    .filter(Boolean)
    .join(' \u2022 ')

  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <Smartphone className="h-5 w-5 text-muted-foreground" />
        </div>
        <div>
          <p className="font-medium">{device.name}</p>
          <p className="text-sm text-muted-foreground">{metadata}</p>
        </div>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={() => onRemove(device)}
          >
            Remove device
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

export function DeviceList() {
  const { data, isLoading, error } = useDevices()
  const revokeMutation = useRevokeDevice()
  const [linkDialogOpen, setLinkDialogOpen] = useState(false)
  const [deviceToRemove, setDeviceToRemove] = useState<DeviceResponse | null>(null)

  const handleRemoveConfirm = () => {
    if (deviceToRemove) {
      revokeMutation.mutate(deviceToRemove.id, {
        onSettled: () => setDeviceToRemove(null),
      })
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Linked Devices</CardTitle>
          <CardDescription>Manage devices connected to your account</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-24">
            <LoadingSpinner size="sm" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Linked Devices</CardTitle>
          <CardDescription>Manage devices connected to your account</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-destructive text-sm">Failed to load devices</p>
        </CardContent>
      </Card>
    )
  }

  const devices = data?.devices ?? []

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Linked Devices</CardTitle>
          <CardDescription>Manage devices connected to your account</CardDescription>
        </CardHeader>
        <CardContent>
          {devices.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Smartphone className="mb-3 h-12 w-12 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">No devices linked yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Link your mobile device to sync data and access your account on the go.
              </p>
              <Button size="sm" className="mt-4 gap-1.5" onClick={() => setLinkDialogOpen(true)}>
                <Plus className="h-4 w-4" />
                Link Device
              </Button>
            </div>
          ) : (
            <>
              <div className="divide-y">
                {devices.map((device) => (
                  <DeviceItem key={device.id} device={device} onRemove={setDeviceToRemove} />
                ))}
              </div>
              <div className="pt-4 border-t mt-4">
                <Button variant="outline" onClick={() => setLinkDialogOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Link new device
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <LinkDeviceDialog open={linkDialogOpen} onOpenChange={setLinkDialogOpen} />

      <AlertDialog
        open={!!deviceToRemove}
        onOpenChange={(open) => !open && setDeviceToRemove(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove device?</AlertDialogTitle>
            <AlertDialogDescription>
              This will sign out {deviceToRemove?.name} and prevent it from syncing. You can re-link
              it later by scanning a new QR code.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveConfirm}
              disabled={revokeMutation.isPending}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {revokeMutation.isPending ? 'Removing...' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
