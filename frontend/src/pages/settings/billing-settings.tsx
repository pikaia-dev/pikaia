import { SettingsPageLayout } from '@/components/settings-page-layout'
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

  const isSubscribed = subscription && subscription.status !== 'none'
  const memberCount = subscription?.quantity || 1

  return (
    <SettingsPageLayout
      title="Billing"
      description="Manage billing information for invoices"
      maxWidth="max-w-2xl"
      isLoading={isLoading}
    >
      <SubscriptionCard subscription={subscription ?? null} memberCount={memberCount} />
      <InvoiceDeliveryForm />
      <BillingAddressForm />
      {isSubscribed && <InvoiceList />}
    </SettingsPageLayout>
  )
}
