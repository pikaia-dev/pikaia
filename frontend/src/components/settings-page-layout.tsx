import type { ReactNode } from 'react'

import { LoadingSpinner } from '@/components/ui/loading-spinner'

interface SettingsPageLayoutProps {
  title: string
  description: string | ReactNode
  maxWidth?: string
  isLoading?: boolean
  error?: Error | null
  children: ReactNode
}

export function SettingsPageLayout({
  title,
  description,
  maxWidth = 'max-w-lg',
  isLoading,
  error,
  children,
}: SettingsPageLayoutProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load data</p>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-muted-foreground">{description}</p>
      </div>

      <div className={`space-y-6 ${maxWidth}`}>{children}</div>
    </div>
  )
}
