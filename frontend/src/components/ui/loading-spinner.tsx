import { cn } from '../../lib/utils'

interface LoadingSpinnerProps {
    /** sm = 24px, md = 32px */
    size?: 'sm' | 'md'
    className?: string
}

/**
 * Reusable loading spinner component.
 * Use size="sm" for inline/settings contexts, size="md" (default) for full-page loading states.
 */
export function LoadingSpinner({ size = 'md', className }: LoadingSpinnerProps) {
    const sizeClass = size === 'sm' ? 'h-6 w-6' : 'h-8 w-8'
    return (
        <div
            className={cn(
                'animate-spin rounded-full border-b-2 border-foreground',
                sizeClass,
                className
            )}
        />
    )
}
