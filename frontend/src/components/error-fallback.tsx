import type { FallbackProps } from 'react-error-boundary'

import { Button } from '@/components/ui/button'

export function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4 max-w-md px-4">
        <h1 className="text-4xl font-bold">Something went wrong</h1>
        <p className="text-muted-foreground">
          An unexpected error occurred. Please try again, or contact support if the problem
          persists.
        </p>
        {import.meta.env.DEV && error instanceof Error && (
          <pre className="mt-4 rounded-md bg-muted p-4 text-left text-sm text-muted-foreground overflow-auto max-h-48">
            {error.message}
          </pre>
        )}
        <Button onClick={resetErrorBoundary}>Try again</Button>
      </div>
    </div>
  )
}
