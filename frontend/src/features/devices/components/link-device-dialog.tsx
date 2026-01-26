import { AlertCircle, Clock } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useInitiateDeviceLink } from '@/features/devices/api/mutations'

interface LinkDeviceDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function LinkDeviceDialog({ open, onOpenChange }: LinkDeviceDialogProps) {
  const initiateMutation = useInitiateDeviceLink()
  const [qrData, setQrData] = useState<{ url: string; expiresAt: Date } | null>(null)
  const [secondsRemaining, setSecondsRemaining] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Store mutate in ref for stable reference
  const mutateRef = useRef(initiateMutation.mutate)
  mutateRef.current = initiateMutation.mutate

  const startCountdown = (expiresInSeconds: number) => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
    }
    setSecondsRemaining(expiresInSeconds)
    intervalRef.current = setInterval(() => {
      setSecondsRemaining((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
  }

  const generateQrCode = () => {
    mutateRef.current(undefined, {
      onSuccess: (data) => {
        setQrData({ url: data.qr_url, expiresAt: new Date(data.expires_at) })
        startCountdown(data.expires_in_seconds)
      },
    })
  }

  // Handle dialog open/close and countdown timer
  useEffect(() => {
    if (!open) return

    // Generate QR code when dialog opens
    mutateRef.current(undefined, {
      onSuccess: (data) => {
        setQrData({ url: data.qr_url, expiresAt: new Date(data.expires_at) })
        startCountdown(data.expires_in_seconds)
      },
    })

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      setQrData(null)
      setSecondsRemaining(0)
    }
  }, [open])

  const isExpired = qrData && secondsRemaining <= 0
  const minutes = Math.floor(secondsRemaining / 60)
  const seconds = secondsRemaining % 60

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Link a device</DialogTitle>
          <DialogDescription>
            Scan this QR code with the Pikaia mobile app to link your device.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col items-center py-6">
          {initiateMutation.isPending ? (
            <div className="flex items-center justify-center h-56">
              <LoadingSpinner size="sm" />
            </div>
          ) : initiateMutation.isError ? (
            <div className="flex flex-col items-center justify-center h-56 text-center">
              <AlertCircle className="h-10 w-10 text-destructive mb-3" />
              <p className="text-sm text-destructive font-medium mb-1">
                {initiateMutation.error?.message?.includes('Too many')
                  ? 'Too many attempts'
                  : 'Failed to generate QR code'}
              </p>
              <p className="text-xs text-muted-foreground mb-4">
                {initiateMutation.error?.message?.includes('Too many')
                  ? 'You can generate up to 5 codes per hour. Try again in an hour.'
                  : 'Please try again.'}
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={generateQrCode}
                disabled={initiateMutation.isPending}
              >
                Try again
              </Button>
            </div>
          ) : isExpired ? (
            <div className="flex flex-col items-center justify-center h-56 text-center">
              <Clock className="h-10 w-10 text-muted-foreground/50 mb-3" />
              <p className="text-sm font-medium mb-1">QR code expired</p>
              <p className="text-xs text-muted-foreground mb-4">
                Generate a new code to continue linking your device.
              </p>
              <Button size="sm" onClick={generateQrCode} disabled={initiateMutation.isPending}>
                Regenerate QR code
              </Button>
            </div>
          ) : qrData ? (
            <>
              <div className="bg-white p-4 rounded-lg">
                <QRCodeSVG value={qrData.url} size={192} level="M" />
              </div>
              <p className="text-sm text-muted-foreground mt-4">
                Expires in {minutes}:{seconds.toString().padStart(2, '0')}
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={generateQrCode}
                disabled={initiateMutation.isPending}
                className="mt-2"
              >
                Regenerate QR code
              </Button>
            </>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}
