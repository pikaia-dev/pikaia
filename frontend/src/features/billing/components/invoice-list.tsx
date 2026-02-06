import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import type { Invoice } from '@/api/types'
import { useApi } from '@/api/use-api'
import { useInvoices } from '@/features/billing/api/queries'
import { InvoiceHistoryCard } from '@/features/billing/components/invoice-history-card'

/**
 * Manages invoice fetching and pagination, delegating display to InvoiceHistoryCard.
 */
export function InvoiceList() {
  const api = useApi()
  const { data: invoicesData, isLoading: invoicesLoading } = useInvoices({
    limit: 6,
  })

  const [additionalInvoices, setAdditionalInvoices] = useState<Invoice[]>([])
  const [invoicesHasMore, setInvoicesHasMore] = useState(false)
  const [loadingMoreInvoices, setLoadingMoreInvoices] = useState(false)

  // Reset additional invoices when base data changes (e.g., refetch, org switch)
  useEffect(() => {
    if (invoicesData) {
      setInvoicesHasMore(invoicesData.has_more)
      setAdditionalInvoices([])
    }
  }, [invoicesData])

  // Combine base invoices with additional loaded invoices
  const allInvoices = [...(invoicesData?.invoices ?? []), ...additionalInvoices]

  const loadMoreInvoices = async () => {
    if (!allInvoices.length || loadingMoreInvoices) return
    setLoadingMoreInvoices(true)
    try {
      const lastInvoice = allInvoices[allInvoices.length - 1]
      const data = await api.listInvoices({
        limit: 6,
        starting_after: lastInvoice.id,
      })
      setAdditionalInvoices((prev) => [...prev, ...data.invoices])
      setInvoicesHasMore(data.has_more)
    } catch {
      toast.error('Failed to load more invoices')
    } finally {
      setLoadingMoreInvoices(false)
    }
  }

  return (
    <InvoiceHistoryCard
      invoices={allInvoices}
      isLoading={invoicesLoading}
      hasMore={invoicesHasMore}
      loadingMore={loadingMoreInvoices}
      onLoadMore={loadMoreInvoices}
    />
  )
}
