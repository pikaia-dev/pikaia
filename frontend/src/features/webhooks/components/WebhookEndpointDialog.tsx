import { zodResolver } from '@hookform/resolvers/zod'
import { Copy, Eye, EyeOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { Button } from '../../../components/ui/button'
import { Checkbox } from '../../../components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../../components/ui/dialog'
import { Input } from '../../../components/ui/input'
import { Label } from '../../../components/ui/label'
import type { WebhookEndpoint, WebhookEndpointWithSecret, WebhookEventType } from '../../../lib/api'
import { useCreateWebhookEndpoint, useUpdateWebhookEndpoint } from '../queries'

const webhookSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  description: z.string().max(500).optional(),
  url: z
    .string()
    .min(1, 'URL is required')
    .refine((val) => val.startsWith('https://'), 'URL must use HTTPS'),
  events: z.array(z.string()).min(1, 'Select at least one event'),
})

type WebhookFormData = z.infer<typeof webhookSchema>

interface WebhookEndpointDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  endpoint?: WebhookEndpoint | null
  events: WebhookEventType[]
}

/**
 * Dialog for creating or editing a webhook endpoint.
 */
export function WebhookEndpointDialog({
  open,
  onOpenChange,
  endpoint,
  events,
}: WebhookEndpointDialogProps) {
  const createMutation = useCreateWebhookEndpoint()
  const updateMutation = useUpdateWebhookEndpoint()
  const isEditing = Boolean(endpoint)

  // State for showing secret after creation
  const [createdEndpoint, setCreatedEndpoint] = useState<WebhookEndpointWithSecret | null>(null)
  const [showSecret, setShowSecret] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<WebhookFormData>({
    resolver: zodResolver(webhookSchema),
    defaultValues: {
      name: '',
      description: '',
      url: '',
      events: [],
    },
  })

  const selectedEvents = watch('events')

  // Reset form when endpoint changes or dialog opens
  useEffect(() => {
    if (open) {
      if (endpoint) {
        reset({
          name: endpoint.name,
          description: endpoint.description || '',
          url: endpoint.url,
          events: endpoint.events,
        })
      } else {
        reset({ name: '', description: '', url: '', events: [] })
      }
      setCreatedEndpoint(null)
      setShowSecret(false)
    }
  }, [open, endpoint, reset])

  const onSubmit = (data: WebhookFormData) => {
    if (isEditing && endpoint) {
      updateMutation.mutate(
        { endpointId: endpoint.id, data },
        {
          onSuccess: () => {
            onOpenChange(false)
          },
        }
      )
    } else {
      createMutation.mutate(data, {
        onSuccess: (newEndpoint) => {
          setCreatedEndpoint(newEndpoint)
        },
      })
    }
  }

  const toggleEvent = (eventType: string) => {
    const current = selectedEvents
    const updated = current.includes(eventType)
      ? current.filter((e) => e !== eventType)
      : [...current, eventType]
    setValue('events', updated, { shouldValidate: true })
  }

  const toggleCategory = (category: string) => {
    const categoryEvents = events.filter((e) => e.category === category).map((e) => e.type)
    const current = selectedEvents
    const allSelected = categoryEvents.every((e) => current.includes(e))
    const updated = allSelected
      ? current.filter((e) => !categoryEvents.includes(e))
      : [...new Set([...current, ...categoryEvents])]
    setValue('events', updated, { shouldValidate: true })
  }

  const selectAllEvents = () => {
    setValue(
      'events',
      events.map((e) => e.type),
      { shouldValidate: true }
    )
  }

  const clearAllEvents = () => {
    setValue('events', [], { shouldValidate: true })
  }

  const copySecret = () => {
    if (createdEndpoint) {
      void navigator.clipboard.writeText(createdEndpoint.secret)
      toast.success('Secret copied to clipboard')
    }
  }

  // Group events by category
  const eventsByCategory = events.reduce<Record<string, WebhookEventType[]>>((acc, event) => {
    if (!acc[event.category]) {
      acc[event.category] = []
    }
    acc[event.category].push(event)
    return acc
  }, {})

  // If we just created an endpoint, show the secret
  if (createdEndpoint) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Endpoint Created</DialogTitle>
            <DialogDescription>
              Save your webhook signing secret. You won&apos;t be able to see it again.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Signing Secret</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  readOnly
                  type={showSecret ? 'text' : 'password'}
                  value={createdEndpoint.secret}
                  className="font-mono text-sm"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    setShowSecret(!showSecret)
                  }}
                >
                  {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
                <Button variant="outline" size="icon" onClick={copySecret}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Use this secret to verify webhook signatures. See the{' '}
                <a href="/docs/webhooks" className="underline">
                  documentation
                </a>{' '}
                for details.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={() => {
                onOpenChange(false)
              }}
            >
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Webhook Endpoint' : 'Add Webhook Endpoint'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the webhook endpoint configuration.'
              : 'Configure a new webhook endpoint to receive events.'}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register('name')} placeholder="My Webhook" />
              {errors.name && (
                <p className="text-sm text-destructive mt-1">{errors.name.message}</p>
              )}
            </div>

            <div>
              <Label htmlFor="description">Description (optional)</Label>
              <Input
                id="description"
                {...register('description')}
                placeholder="Brief description of this webhook"
              />
            </div>

            <div>
              <Label htmlFor="url">Endpoint URL</Label>
              <Input id="url" {...register('url')} placeholder="https://example.com/webhooks" />
              {errors.url && <p className="text-sm text-destructive mt-1">{errors.url.message}</p>}
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>Events</Label>
                <div className="flex gap-2">
                  <Button type="button" variant="ghost" size="sm" onClick={selectAllEvents}>
                    Select All
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={clearAllEvents}>
                    Clear
                  </Button>
                </div>
              </div>
              {errors.events && (
                <p className="text-sm text-destructive mb-2">{errors.events.message}</p>
              )}
              <div className="border rounded-md p-4 space-y-4 max-h-64 overflow-y-auto">
                {Object.entries(eventsByCategory).map(([category, categoryEvents]) => {
                  const allCategorySelected = categoryEvents.every((e) =>
                    selectedEvents.includes(e.type)
                  )
                  const someCategorySelected = categoryEvents.some((e) =>
                    selectedEvents.includes(e.type)
                  )
                  return (
                    <div key={category}>
                      <div className="flex items-center gap-2 mb-2">
                        <Checkbox
                          id={`cat-${category}`}
                          checked={allCategorySelected}
                          // Show indeterminate state
                          data-state={
                            allCategorySelected
                              ? 'checked'
                              : someCategorySelected
                                ? 'indeterminate'
                                : 'unchecked'
                          }
                          onCheckedChange={() => {
                            toggleCategory(category)
                          }}
                        />
                        <Label
                          htmlFor={`cat-${category}`}
                          className="font-medium capitalize cursor-pointer"
                        >
                          {category}
                        </Label>
                      </div>
                      <div className="ml-6 space-y-1">
                        {categoryEvents.map((event) => (
                          <div key={event.type} className="flex items-start gap-2">
                            <Checkbox
                              id={event.type}
                              checked={selectedEvents.includes(event.type)}
                              onCheckedChange={() => {
                                toggleEvent(event.type)
                              }}
                            />
                            <div className="grid gap-0.5">
                              <Label
                                htmlFor={event.type}
                                className="font-mono text-sm cursor-pointer"
                              >
                                {event.type}
                              </Label>
                              <p className="text-xs text-muted-foreground">{event.description}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false)
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || createMutation.isPending || updateMutation.isPending}
            >
              {createMutation.isPending || updateMutation.isPending
                ? 'Saving...'
                : isEditing
                  ? 'Save Changes'
                  : 'Create Endpoint'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
