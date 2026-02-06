import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useSubscription } from '@/features/billing/api/queries'
import { BillingAddressForm } from '@/features/billing/components/billing-address-form'
import { InvoiceDeliveryForm } from '@/features/billing/components/invoice-delivery-form'
import { InvoiceList } from '@/features/billing/components/invoice-list'
import { SubscriptionCard } from '@/features/billing/components/subscription-card'
import { useOrganization } from '@/features/organization/api/queries'

export default function BillingSettings() {
  const { isLoading: orgLoading } = useOrganization()
  const { data: subscription, isLoading: subLoading } = useSubscription()

  const isLoading = orgLoading || subLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  const isSubscribed = subscription && subscription.status !== 'none'
  const memberCount = subscription?.quantity || 1

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Billing</h1>
        <p className="text-muted-foreground">Manage billing information for invoices</p>
      </div>

      <div className="space-y-6 max-w-2xl">
        <SubscriptionCard subscription={subscription ?? null} memberCount={memberCount} />
        <InvoiceDeliveryForm />
        <BillingAddressForm />
        {isSubscribed && <InvoiceList />}
      </div>
    </div>
  )
}
