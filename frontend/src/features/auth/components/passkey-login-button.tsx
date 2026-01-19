import { Fingerprint } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'

import {
  isWebAuthnSupported,
  setPasskeyHint,
  useAuthenticateWithPasskey,
} from '@/features/auth/hooks/use-passkey-auth'

interface PasskeyLoginButtonProps {
  onSuccess: (result: {
    session_token: string
    session_jwt: string
    member_id: string
    organization_id: string
    user_id: number
  }) => void
  variant?: 'primary' | 'secondary' | 'link'
  className?: string
}

export function PasskeyLoginButton({
  onSuccess,
  variant = 'primary',
  className = '',
}: PasskeyLoginButtonProps) {
  const [isAuthenticating, setIsAuthenticating] = useState(false)
  const authenticateMutation = useAuthenticateWithPasskey()

  if (!isWebAuthnSupported()) {
    return null
  }

  const handleClick = async () => {
    setIsAuthenticating(true)
    try {
      const result = await authenticateMutation.mutateAsync({})
      // Remember that this user has a passkey
      setPasskeyHint()
      // Pass full result including session tokens
      onSuccess(result)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Passkey authentication failed')
    } finally {
      setIsAuthenticating(false)
    }
  }

  if (variant === 'link') {
    return (
      <button
        type="button"
        onClick={() => void handleClick()}
        disabled={isAuthenticating}
        className={`text-sm text-muted-foreground hover:text-foreground underline-offset-4 hover:underline ${className}`}
      >
        <Fingerprint className="inline-block h-4 w-4 mr-1" />
        {isAuthenticating ? 'Authenticating...' : 'Have a passkey?'}
      </button>
    )
  }

  if (variant === 'secondary') {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => void handleClick()}
        disabled={isAuthenticating}
        className={className}
      >
        <Fingerprint className="h-4 w-4 mr-2" />
        {isAuthenticating ? '...' : 'Passkey'}
      </Button>
    )
  }

  // Primary variant - prominent button
  return (
    <Button
      type="button"
      onClick={() => void handleClick()}
      disabled={isAuthenticating}
      className={`w-full ${className}`}
    >
      <Fingerprint className="h-5 w-5 mr-2" />
      {isAuthenticating ? 'Authenticating...' : 'Sign in with Passkey'}
    </Button>
  )
}
