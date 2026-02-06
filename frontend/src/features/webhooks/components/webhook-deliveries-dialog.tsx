import { AlertTriangle, Check, Clock, RefreshCw } from 'lucide-react'
import type { WebhookDelivery, WebhookEndpoint } from '@/api/types'
import { StatusBadge } from '@/components/status-badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useWebhookDeliveries } from '@/features/webhooks/api/queries'
import { formatDateTime } from '@/lib/format'

interface WebhookDeliveriesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  endpoint: WebhookEndpoint | null
}

function getStatusIcon(status: WebhookDelivery['status']) {
  switch (status) {
    case 'success':
      return <Check className="h-4 w-4 text-green-600" />
    case 'failure':
      return <AlertTriangle className="h-4 w-4 text-red-600" />
    case 'pending':
      return <Clock className="h-4 w-4 text-amber-600" />
    default:
      return null
  }
}

function getStatusBadge(delivery: WebhookDelivery) {
  switch (delivery.status) {
    case 'success':
      return (
        <StatusBadge variant="success" icon={getStatusIcon(delivery.status)}>
          {delivery.http_status}
        </StatusBadge>
      )
    case 'failure':
      return (
        <StatusBadge variant="danger" icon={getStatusIcon(delivery.status)}>
          {delivery.http_status ? String(delivery.http_status) : delivery.error_type || 'Error'}
        </StatusBadge>
      )
    case 'pending':
      return (
        <StatusBadge variant="warning" icon={getStatusIcon(delivery.status)}>
          Retry #{delivery.attempt_number}
        </StatusBadge>
      )
    default:
      return <StatusBadge variant="neutral">{String(delivery.status)}</StatusBadge>
  }
}

/**
 * Dialog for viewing webhook delivery history.
 */
export function WebhookDeliveriesDialog({
  open,
  onOpenChange,
  endpoint,
}: WebhookDeliveriesDialogProps) {
  const { data, isLoading, error, refetch, isFetching } = useWebhookDeliveries(
    endpoint?.id ?? '',
    50
  )

  const deliveries = data?.deliveries ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Delivery History</DialogTitle>
              <DialogDescription>Recent webhook deliveries for {endpoint?.name}</DialogDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void refetch()
              }}
              disabled={isFetching}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size="sm" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-destructive">Failed to load deliveries</p>
            </div>
          ) : deliveries.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-muted-foreground">No deliveries yet</p>
            </div>
          ) : (
            <div className="border rounded-md overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 sticky top-0">
                  <tr>
                    <th className="text-left p-3 font-medium">Event</th>
                    <th className="text-left p-3 font-medium">Status</th>
                    <th className="text-left p-3 font-medium">Duration</th>
                    <th className="text-left p-3 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.map((delivery) => (
                    <tr key={delivery.id} className="border-t">
                      <td className="p-3">
                        <div>
                          <p className="font-mono text-sm">{delivery.event_type}</p>
                          <p className="text-xs text-muted-foreground font-mono">
                            {delivery.event_id}
                          </p>
                        </div>
                      </td>
                      <td className="p-3">{getStatusBadge(delivery)}</td>
                      <td className="p-3 text-muted-foreground">
                        {delivery.duration_ms ? `${String(delivery.duration_ms)}ms` : '—'}
                      </td>
                      <td className="p-3 text-muted-foreground">
                        {formatDateTime(delivery.attempted_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
