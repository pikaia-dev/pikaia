import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type StatusBadgeVariant = 'success' | 'warning' | 'danger' | 'neutral' | 'info'

const VARIANT_CLASSES: Record<StatusBadgeVariant, string> = {
  success: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  warning: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  danger: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  neutral: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  info: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
}

interface StatusBadgeProps {
  variant: StatusBadgeVariant
  children: ReactNode
  icon?: ReactNode
  className?: string
}

/**
 * Consistent status badge used across the app for displaying statuses
 * such as active/inactive, paid/unpaid, success/failure, etc.
 */
export function StatusBadge({ variant, children, icon, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        VARIANT_CLASSES[variant],
        className
      )}
    >
      {icon}
      {children}
    </span>
  )
}
