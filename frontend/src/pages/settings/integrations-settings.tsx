import { Plus } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { WebhookDeliveriesDialog } from '@/features/webhooks/components/webhook-deliveries-dialog'
import { WebhookEndpointDialog } from '@/features/webhooks/components/webhook-endpoint-dialog'
import { WebhookEndpointsList } from '@/features/webhooks/components/webhook-endpoints-list'
import { useWebhookEndpoints, useWebhookEvents } from '@/features/webhooks/queries'
import type { WebhookEndpoint } from '@/lib/api'

export default function IntegrationsSettings() {
  const {
    data: endpointsData,
    isLoading: endpointsLoading,
    error: endpointsError,
  } = useWebhookEndpoints()
  const { data: eventsData, isLoading: eventsLoading } = useWebhookEvents()

  // Dialog state
  const [endpointDialogOpen, setEndpointDialogOpen] = useState(false)
  const [editingEndpoint, setEditingEndpoint] = useState<WebhookEndpoint | null>(null)
  const [deliveriesDialogOpen, setDeliveriesDialogOpen] = useState(false)
  const [viewingEndpoint, setViewingEndpoint] = useState<WebhookEndpoint | null>(null)

  const endpoints = endpointsData?.endpoints ?? []
  const events = eventsData?.events ?? []

  const handleAddEndpoint = () => {
    setEditingEndpoint(null)
    setEndpointDialogOpen(true)
  }

  const handleEditEndpoint = (endpoint: WebhookEndpoint) => {
    setEditingEndpoint(endpoint)
    setEndpointDialogOpen(true)
  }

  const handleViewDeliveries = (endpoint: WebhookEndpoint) => {
    setViewingEndpoint(endpoint)
    setDeliveriesDialogOpen(true)
  }

  if (endpointsLoading || eventsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  if (endpointsError) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load integrations</p>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="text-muted-foreground">Connect external services via webhooks</p>
      </div>

      <div className="space-y-6 max-w-4xl">
        {/* Add Endpoint Card */}
        <Card>
          <CardHeader className="flex flex-row items-start justify-between">
            <div>
              <CardTitle className="text-base">Webhooks</CardTitle>
              <CardDescription>
                Receive real-time notifications when events occur in your organization
              </CardDescription>
            </div>
            <Button onClick={handleAddEndpoint}>
              <Plus className="h-4 w-4 mr-2" />
              Add Endpoint
            </Button>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Configure webhook endpoints to receive HTTP POST requests when events like member
              changes, billing updates, or organization changes occur. All webhooks are signed with
              HMAC-SHA256 for security.
            </p>
          </CardContent>
        </Card>

        {/* Endpoints List */}
        <WebhookEndpointsList
          endpoints={endpoints}
          events={events}
          onEdit={handleEditEndpoint}
          onViewDeliveries={handleViewDeliveries}
        />

        {/* Endpoint Dialog */}
        <WebhookEndpointDialog
          open={endpointDialogOpen}
          onOpenChange={setEndpointDialogOpen}
          endpoint={editingEndpoint}
          events={events}
        />

        {/* Deliveries Dialog */}
        <WebhookDeliveriesDialog
          open={deliveriesDialogOpen}
          onOpenChange={setDeliveriesDialogOpen}
          endpoint={viewingEndpoint}
        />
      </div>
    </div>
  )
}
