import {
  AlertTriangle,
  Check,
  Clock,
  ExternalLink,
  MoreVertical,
  Pause,
  Play,
  Send,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import type { WebhookEndpoint, WebhookEventType } from '@/api/types'
import { StatusBadge } from '@/components/status-badge'
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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  useDeleteWebhookEndpoint,
  useTestWebhookEndpoint,
  useUpdateWebhookEndpoint,
} from '@/features/webhooks/api/mutations'

interface WebhookEndpointsListProps {
  endpoints: WebhookEndpoint[]
  events: WebhookEventType[]
  onEdit: (endpoint: WebhookEndpoint) => void
  onViewDeliveries: (endpoint: WebhookEndpoint) => void
}

/**
 * Table component for displaying webhook endpoints.
 */
export function WebhookEndpointsList({
  endpoints,
  events,
  onEdit,
  onViewDeliveries,
}: WebhookEndpointsListProps) {
  const updateMutation = useUpdateWebhookEndpoint()
  const deleteMutation = useDeleteWebhookEndpoint()
  const testMutation = useTestWebhookEndpoint()

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [endpointToDelete, setEndpointToDelete] = useState<WebhookEndpoint | null>(null)
  const [testDialogOpen, setTestDialogOpen] = useState(false)
  const [endpointToTest, setEndpointToTest] = useState<WebhookEndpoint | null>(null)

  const handleToggleActive = (endpoint: WebhookEndpoint) => {
    updateMutation.mutate({
      endpointId: endpoint.id,
      data: { active: !endpoint.active },
    })
  }

  const openDeleteDialog = (endpoint: WebhookEndpoint) => {
    setEndpointToDelete(endpoint)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = () => {
    if (!endpointToDelete) return
    deleteMutation.mutate(endpointToDelete.id, {
      onSettled: () => {
        setDeleteDialogOpen(false)
        setEndpointToDelete(null)
      },
    })
  }

  const openTestDialog = (endpoint: WebhookEndpoint) => {
    setEndpointToTest(endpoint)
    setTestDialogOpen(true)
  }

  const handleSendTest = (eventType: string) => {
    if (!endpointToTest) return
    testMutation.mutate(
      { endpointId: endpointToTest.id, data: { event_type: eventType } },
      {
        onSettled: () => {
          setTestDialogOpen(false)
          setEndpointToTest(null)
        },
      }
    )
  }

  const getStatusBadge = (endpoint: WebhookEndpoint) => {
    if (!endpoint.active) {
      return (
        <StatusBadge variant="neutral" icon={<Pause className="h-3 w-3" />}>
          Disabled
        </StatusBadge>
      )
    }
    if (endpoint.consecutive_failures >= 5) {
      return (
        <StatusBadge variant="danger" icon={<AlertTriangle className="h-3 w-3" />}>
          Failing
        </StatusBadge>
      )
    }
    if (endpoint.last_delivery_status === 'success') {
      return (
        <StatusBadge variant="success" icon={<Check className="h-3 w-3" />}>
          Active
        </StatusBadge>
      )
    }
    if (endpoint.last_delivery_status === 'failure') {
      return (
        <StatusBadge variant="warning" icon={<AlertTriangle className="h-3 w-3" />}>
          Warning
        </StatusBadge>
      )
    }
    return (
      <StatusBadge variant="neutral" icon={<Clock className="h-3 w-3" />}>
        No deliveries
      </StatusBadge>
    )
  }

  if (endpoints.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No webhook endpoints configured yet.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Webhook Endpoints</CardTitle>
          <CardDescription>
            {endpoints.length} endpoint{endpoints.length !== 1 ? 's' : ''} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-3 font-medium">Name</th>
                  <th className="text-left p-3 font-medium">URL</th>
                  <th className="text-left p-3 font-medium">Events</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-right p-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map((endpoint) => (
                  <tr
                    key={endpoint.id}
                    className={`border-t ${!endpoint.active ? 'opacity-60' : ''}`}
                  >
                    <td className="p-3">
                      <div>
                        <p className="font-medium">{endpoint.name}</p>
                        {endpoint.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                            {endpoint.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="p-3">
                      <a
                        href={endpoint.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground truncate max-w-[250px]"
                      >
                        <span className="truncate">{endpoint.url}</span>
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    </td>
                    <td className="p-3">
                      <span className="text-muted-foreground">
                        {endpoint.events.length} event{endpoint.events.length !== 1 ? 's' : ''}
                      </span>
                    </td>
                    <td className="p-3">{getStatusBadge(endpoint)}</td>
                    <td className="p-3 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => {
                              onEdit(endpoint)
                            }}
                          >
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => {
                              onViewDeliveries(endpoint)
                            }}
                          >
                            View Deliveries
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => {
                              openTestDialog(endpoint)
                            }}
                          >
                            <Send className="h-4 w-4 mr-2" />
                            Send Test
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => {
                              handleToggleActive(endpoint)
                            }}
                          >
                            {endpoint.active ? (
                              <>
                                <Pause className="h-4 w-4 mr-2" />
                                Disable
                              </>
                            ) : (
                              <>
                                <Play className="h-4 w-4 mr-2" />
                                Enable
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => {
                              openDeleteDialog(endpoint)
                            }}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete webhook endpoint</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{endpointToDelete?.name}</strong>? This action
              cannot be undone and all delivery history will be lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Test Event Dialog */}
      <AlertDialog open={testDialogOpen} onOpenChange={setTestDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Send test webhook</AlertDialogTitle>
            <AlertDialogDescription>
              Select an event type to send to <strong>{endpointToTest?.name}</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="grid gap-2 py-4 max-h-64 overflow-y-auto">
            {events.map((event) => (
              <Button
                key={event.type}
                variant="outline"
                className="justify-start h-auto py-2"
                onClick={() => {
                  handleSendTest(event.type)
                }}
                disabled={testMutation.isPending}
              >
                <div className="text-left">
                  <p className="font-mono text-sm">{event.type}</p>
                  <p className="text-xs text-muted-foreground">{event.description}</p>
                </div>
              </Button>
            ))}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
