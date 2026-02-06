import type { Invoice } from '@/api/types'
import { StatusBadge } from '@/components/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { formatDateLong } from '@/lib/format'

interface InvoiceHistoryCardProps {
  invoices: Invoice[]
  isLoading: boolean
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
}

/**
 * Card component for displaying invoice history with pagination.
 */
export function InvoiceHistoryCard({
  invoices,
  isLoading,
  hasMore,
  loadingMore,
  onLoadMore,
}: InvoiceHistoryCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Invoice History</CardTitle>
        <CardDescription>View and download your past invoices</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="sm" />
          </div>
        ) : invoices.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">
            No invoices yet. Your first invoice will appear here after your subscription renews.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 font-medium">Invoice</th>
                    <th className="text-left py-2 font-medium">Status</th>
                    <th className="text-right py-2 font-medium">Amount</th>
                    <th className="text-right py-2 font-medium">Date</th>
                    <th className="text-right py-2 font-medium sr-only">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.id} className="border-b last:border-0">
                      <td className="py-3">
                        <span className="font-mono text-xs">
                          {invoice.number || invoice.id.slice(-8)}
                        </span>
                      </td>
                      <td className="py-3">
                        <StatusBadge
                          variant={
                            invoice.status === 'paid'
                              ? 'success'
                              : invoice.status === 'open'
                                ? 'warning'
                                : 'neutral'
                          }
                        >
                          {invoice.status.charAt(0).toUpperCase() + invoice.status.slice(1)}
                        </StatusBadge>
                      </td>
                      <td className="py-3 text-right">
                        {new Intl.NumberFormat(undefined, {
                          style: 'currency',
                          currency: invoice.currency.toUpperCase(),
                        }).format(invoice.amount_paid / 100)}
                      </td>
                      <td className="py-3 text-right text-muted-foreground">
                        {formatDateLong(invoice.created)}
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {invoice.hosted_invoice_url && (
                            <a
                              href={invoice.hosted_invoice_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-primary hover:underline"
                            >
                              View
                            </a>
                          )}
                          {invoice.invoice_pdf && (
                            <a
                              href={invoice.invoice_pdf}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-primary hover:underline"
                            >
                              PDF
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {hasMore && (
              <div className="flex justify-center pt-2">
                <Button variant="outline" size="sm" onClick={onLoadMore} disabled={loadingMore}>
                  {loadingMore ? 'Loading...' : 'Load more'}
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
