import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold">404</h1>
        <p className="text-muted-foreground">Page not found</p>
        <Button asChild>
          <Link to="/">Go home</Link>
        </Button>
      </div>
    </div>
  )
}
