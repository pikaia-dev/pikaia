import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import type { Invoice } from '@/api/types'
import { useInvoices } from '@/features/billing/api/queries'
import { InvoiceHistoryCard } from '@/features/billing/components/invoice-history-card'

/**
 * Manages invoice fetching and pagination, delegating display to InvoiceHistoryCard.
 */
export function InvoiceList() {
  const { data: invoicesData, isLoading: invoicesLoading } = useInvoices({
    limit: 6,
  })

  const [additionalInvoices, setAdditionalInvoices] = useState<Invoice[]>([])
  const [invoicesHasMore, setInvoicesHasMore] = useState(false)
  const [loadingMoreInvoices, setLoadingMoreInvoices] = useState(false)

  // Update invoices pagination state when data changes
  useEffect(() => {
    if (invoicesData) {
      setInvoicesHasMore(invoicesData.has_more)
    }
  }, [invoicesData])

  // Combine base invoices with additional loaded invoices
  const allInvoices = [...(invoicesData?.invoices ?? []), ...additionalInvoices]

  const loadMoreInvoices = async () => {
    if (!allInvoices.length || loadingMoreInvoices) return
    setLoadingMoreInvoices(true)
    try {
      const lastInvoice = allInvoices[allInvoices.length - 1]
      const session = localStorage.getItem('stytch_session_jwt') ?? ''
      const response = await fetch(
        `/api/v1/billing/invoices?limit=6&starting_after=${lastInvoice.id}`,
        {
          headers: {
            Authorization: `Bearer ${session}`,
          },
        }
      )
      if (!response.ok) throw new Error('Failed to load more invoices')
      const data = (await response.json()) as {
        invoices: Invoice[]
        has_more: boolean
      }
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
