import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import { type EmailFormData, emailSchema } from '../forms/schema'

interface EmailLoginFormProps {
  onSubmit: (email: string) => void
  isLoading: boolean
  error: string | null
}

export function EmailLoginForm({ onSubmit, isLoading, error }: EmailLoginFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EmailFormData>({
    resolver: zodResolver(emailSchema),
  })

  const onFormSubmit = (data: EmailFormData) => {
    onSubmit(data.email)
  }

  return (
    <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="email" className="block text-sm font-medium">
          Email address
        </label>
        <Input
          {...register('email')}
          id="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          autoFocus
          disabled={isLoading}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              void handleSubmit(onFormSubmit)()
            }
          }}
        />
        {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>

      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? 'Sending...' : 'Continue with email'}
      </Button>
    </form>
  )
}
