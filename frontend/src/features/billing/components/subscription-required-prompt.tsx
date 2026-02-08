import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function SubscriptionRequiredPrompt() {
  const navigate = useNavigate()

  return (
    <div className="flex items-center justify-center py-12">
      <Card className="max-w-md w-full">
        <CardHeader>
          <CardTitle>Subscription Required</CardTitle>
          <CardDescription>
            An active subscription is required to access this feature. Subscribe to unlock full
            access.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void navigate('/settings/billing')}>View Plans</Button>
        </CardContent>
      </Card>
    </div>
  )
}
