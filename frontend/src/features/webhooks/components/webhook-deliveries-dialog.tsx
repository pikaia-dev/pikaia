import { AlertTriangle, Check, Clock, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useWebhookDeliveries } from '@/features/webhooks/queries'
import type { WebhookDelivery, WebhookEndpoint } from '@/lib/api'

interface WebhookDeliveriesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  endpoint: WebhookEndpoint | null
}

function formatDate(dateString: string | null): string {
  if (!dateString) return '—'
  const date = new Date(dateString)
  return date.toLocaleString()
}

function getStatusIcon(status: WebhookDelivery['status']) {
  switch (status) {
    case 'success':
      return <Check className="h-4 w-4 text-green-600" />
    case 'failure':
      return <AlertTriangle className="h-4 w-4 text-red-600" />
    case 'pending':
      return <Clock className="h-4 w-4 text-amber-600" />
  }
}

function getStatusBadge(delivery: WebhookDelivery) {
  switch (delivery.status) {
    case 'success':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
          {getStatusIcon(delivery.status)}
          {delivery.http_status}
        </span>
      )
    case 'failure':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
          {getStatusIcon(delivery.status)}
          {delivery.http_status ? String(delivery.http_status) : delivery.error_type || 'Error'}
        </span>
      )
    case 'pending':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
          {getStatusIcon(delivery.status)}
          Retry #{delivery.attempt_number}
        </span>
      )
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
                        {formatDate(delivery.attempted_at)}
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
