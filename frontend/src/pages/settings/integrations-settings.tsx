import { Plus } from 'lucide-react'
import { useState } from 'react'
import type { WebhookEndpoint } from '@/api/types'
import { SettingsPageLayout } from '@/components/settings-page-layout'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useWebhookEndpoints, useWebhookEvents } from '@/features/webhooks/api/queries'
import { WebhookDeliveriesDialog } from '@/features/webhooks/components/webhook-deliveries-dialog'
import { WebhookEndpointDialog } from '@/features/webhooks/components/webhook-endpoint-dialog'
import { WebhookEndpointsList } from '@/features/webhooks/components/webhook-endpoints-list'

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

  return (
    <SettingsPageLayout
      title="Integrations"
      description="Connect external services via webhooks"
      maxWidth="max-w-4xl"
      isLoading={endpointsLoading || eventsLoading}
      error={endpointsError}
    >
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
    </SettingsPageLayout>
  )
}
