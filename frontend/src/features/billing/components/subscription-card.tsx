import { useState } from 'react'
import type { SubscriptionInfo } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useConfirmSubscription, useCreatePortalSession } from '@/features/billing/api/mutations'
import { formatDateLong } from '@/lib/format'
import { PaymentForm } from './payment-form'

interface SubscriptionCardProps {
  subscription: SubscriptionInfo | null
  memberCount: number
}

/**
 * Card component for displaying and managing subscription status.
 * Shows upgrade form, active subscription details, or free plan.
 */
export function SubscriptionCard({ subscription, memberCount }: SubscriptionCardProps) {
  const [showUpgradeForm, setShowUpgradeForm] = useState(false)
  const createPortalMutation = useCreatePortalSession()
  const confirmSubscriptionMutation = useConfirmSubscription()

  const isSubscribed = subscription && subscription.status !== 'none'

  const handleUpgradeSuccess = (subscriptionId: string) => {
    setShowUpgradeForm(false)
    confirmSubscriptionMutation.mutate({ subscription_id: subscriptionId })
  }

  const handleManageSubscription = () => {
    createPortalMutation.mutate(
      { return_url: `${window.location.origin}/settings/billing` },
      {
        onSuccess: (data) => {
          window.location.href = data.portal_url
        },
      }
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Subscription</CardTitle>
        <CardDescription>
          {isSubscribed ? 'Manage your subscription and billing' : 'Upgrade to unlock all features'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {showUpgradeForm ? (
          <div className="space-y-4">
            <div className="border-b pb-4 mb-4">
              <h3 className="font-medium">Subscribe to Pro Plan</h3>
              <p className="text-sm text-muted-foreground">
                ${10 * memberCount}/month for {memberCount} {memberCount === 1 ? 'seat' : 'seats'}
              </p>
            </div>
            <PaymentForm
              quantity={memberCount}
              onSuccess={handleUpgradeSuccess}
              onCancel={() => {
                setShowUpgradeForm(false)
              }}
            />
          </div>
        ) : isSubscribed ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">Pro Plan</span>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      subscription.status === 'active'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : subscription.status === 'past_due'
                          ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                          : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                    }`}
                  >
                    {subscription.status === 'active'
                      ? 'Active'
                      : subscription.status === 'past_due'
                        ? 'Past Due'
                        : subscription.status === 'trialing'
                          ? 'Trial'
                          : subscription.status}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {subscription.quantity} {subscription.quantity === 1 ? 'seat' : 'seats'}
                  {subscription.current_period_end && (
                    <>
                      {' · '}
                      {subscription.cancel_at_period_end
                        ? `Cancels ${formatDateLong(subscription.current_period_end)}`
                        : `Renews ${formatDateLong(subscription.current_period_end)}`}
                    </>
                  )}
                </p>
              </div>
              <Button
                variant="outline"
                onClick={handleManageSubscription}
                disabled={createPortalMutation.isPending}
              >
                {createPortalMutation.isPending ? 'Loading...' : 'Manage Subscription'}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Free Plan</p>
              <p className="text-sm text-muted-foreground">
                {memberCount} {memberCount === 1 ? 'member' : 'members'}
              </p>
            </div>
            <Button
              onClick={() => {
                setShowUpgradeForm(true)
              }}
            >
              Upgrade to Pro
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
