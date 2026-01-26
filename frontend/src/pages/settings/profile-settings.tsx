import { useStytchMemberSession } from '@stytch/react/b2b'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ImageUploader } from '@/components/ui/image-uploader'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { PhoneNumberInput } from '@/components/ui/phone-number-input'
import { useCurrentUser } from '@/features/auth/api/queries'
import { DeviceList } from '@/features/devices/components/device-list'
import {
  useSendPhoneOtp,
  useStartEmailUpdate,
  useUpdateProfile,
  useVerifyPhoneOtp,
} from '@/features/profile/api/mutations'
import { PasskeySettings } from '@/features/settings/components/passkey-settings'

// Delay before updating state after dialog close animation
const DIALOG_CLOSE_DELAY_MS = 150

export default function ProfileSettings() {
  const { session } = useStytchMemberSession()
  const { data: userData, isLoading, error } = useCurrentUser()
  const updateProfileMutation = useUpdateProfile()
  const sendPhoneOtpMutation = useSendPhoneOtp()
  const verifyPhoneOtpMutation = useVerifyPhoneOtp()
  const startEmailUpdateMutation = useStartEmailUpdate()

  // Detect if user logged in with passkey (trusted_auth_token type)
  // Passkey sessions are immutable and cannot have phone factors added
  const isPasskeySession = session?.authentication_factors.some(
    (factor) => factor.type === 'trusted_auth_token'
  )

  // Edited values (null = use server value)
  const [editedName, setEditedName] = useState<string | null>(null)
  const [editedPhoneNumber, setEditedPhoneNumber] = useState<string | null>(null)
  const [editedEmail, setEditedEmail] = useState<string | null>(null)
  const [editedAvatarUrl, setEditedAvatarUrl] = useState<string | null>(null)

  // Phone verification dialog state
  const [showVerifyDialog, setShowVerifyDialog] = useState(false)
  const [otpCode, setOtpCode] = useState('')
  const [pendingPhone, setPendingPhone] = useState('')
  const otpInputRef = useRef<HTMLInputElement>(null)

  // Derive current values
  const name = editedName ?? userData?.user.name ?? ''
  const email = userData?.user.email ?? ''
  const newEmail = editedEmail ?? email
  const phoneNumber = editedPhoneNumber ?? userData?.user.phone_number ?? ''
  const savedPhoneNumber = userData?.user.phone_number ?? ''
  const avatarUrl = editedAvatarUrl ?? userData?.user.avatar_url ?? ''

  const isNameChanged = editedName !== null && editedName !== userData?.user.name
  const isPhoneChanged = phoneNumber !== savedPhoneNumber
  const isEmailChanged = newEmail.toLowerCase() !== email.toLowerCase()

  const handleSubmit = () => {
    updateProfileMutation.mutate(
      { name },
      {
        onSuccess: () => {
          setEditedName(null)
        },
      }
    )
  }

  const handleStartEmailUpdate = () => {
    if (!newEmail || !isEmailChanged) return

    startEmailUpdateMutation.mutate(newEmail, {
      onSuccess: () => {
        // Reset to current email (change won't take effect until verified)
        setEditedEmail(null)
      },
    })
  }

  const handleVerifyPhone = () => {
    if (!phoneNumber) return

    sendPhoneOtpMutation.mutate(phoneNumber, {
      onSuccess: () => {
        setPendingPhone(phoneNumber)
        setOtpCode('')
        setShowVerifyDialog(true)
        toast.success('Verification code sent!')
        // Focus OTP input after dialog opens
        setTimeout(() => otpInputRef.current?.focus(), 100)
      },
    })
  }

  const handleVerifyOtp = () => {
    if (!otpCode || otpCode.length !== 6) {
      toast.error('Please enter a 6-digit code')
      return
    }

    verifyPhoneOtpMutation.mutate(
      { phone_number: pendingPhone, otp_code: otpCode },
      {
        onSuccess: (updatedUser) => {
          // Close dialog first, then update state after animation
          setShowVerifyDialog(false)
          // Update phone state after dialog close animation
          setTimeout(() => {
            setEditedPhoneNumber(updatedUser.phone_number)
            setOtpCode('')
            setPendingPhone('')
          }, DIALOG_CLOSE_DELAY_MS)
        },
      }
    )
  }

  const handleResendOtp = () => {
    sendPhoneOtpMutation.mutate(pendingPhone, {
      onSuccess: () => {
        setOtpCode('')
        toast.success('New verification code sent!')
        setTimeout(() => otpInputRef.current?.focus(), 100)
      },
    })
  }

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
        <p className="text-destructive">Failed to load profile</p>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Profile</h1>
        <p className="text-muted-foreground">Manage your personal information</p>
      </div>

      <div className="space-y-6 max-w-lg">
        {/* Avatar Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Profile Picture</CardTitle>
            <CardDescription>Upload a photo to personalize your account</CardDescription>
          </CardHeader>
          <CardContent>
            <ImageUploader type="avatar" value={avatarUrl} onChange={setEditedAvatarUrl} />
          </CardContent>
        </Card>

        {/* Personal Details Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Personal Details</CardTitle>
            <CardDescription>Update your profile information</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium mb-1">
                Display name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => {
                  setEditedName(e.target.value)
                }}
                className="w-full h-10 px-3 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="Your name"
              />
              {isNameChanged && (
                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={updateProfileMutation.isPending}
                  className="mt-2 h-10"
                >
                  {updateProfileMutation.isPending ? 'Saving...' : 'Save name'}
                </Button>
              )}
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-1">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={newEmail}
                onChange={(e) => {
                  setEditedEmail(e.target.value)
                }}
                className="w-full h-10 px-3 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="your@email.com"
              />
              {/* Show status based on current state */}
              {!isEmailChanged && (
                <p className="text-xs text-muted-foreground mt-1">
                  Changing your email requires verification via magic link
                </p>
              )}
              {isEmailChanged && newEmail && (
                <>
                  <p className="text-xs text-amber-600 mt-2 flex items-center gap-1.5">
                    <svg
                      className="h-3.5 w-3.5"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                      aria-hidden="true"
                    >
                      <path
                        fillRule="evenodd"
                        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
                        clipRule="evenodd"
                      />
                    </svg>
                    A verification link will be sent to {newEmail}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    If you signed in with Google, changing email will disconnect that login method.
                  </p>
                  <Button
                    type="button"
                    onClick={handleStartEmailUpdate}
                    disabled={startEmailUpdateMutation.isPending}
                    className="mt-2 h-10"
                  >
                    {startEmailUpdateMutation.isPending ? 'Sending...' : 'Send verification link'}
                  </Button>
                </>
              )}
            </div>

            {/* Phone Number */}
            <div>
              <span className="block text-sm font-medium mb-1">Phone number</span>
              <PhoneNumberInput
                value={phoneNumber}
                onChange={setEditedPhoneNumber}
                disabled={isPasskeySession}
              />
              {/* Passkey session warning - phone verification not available */}
              {isPasskeySession && (
                <Alert className="mt-3 border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950">
                  <AlertDescription className="text-amber-800 dark:text-amber-200 text-xs">
                    Phone verification is not available when logged in with a passkey. To add or
                    update your phone number, please log out and sign in with email instead.
                  </AlertDescription>
                </Alert>
              )}
              {/* Show status based on current state (only if not passkey session) */}
              {!isPasskeySession && savedPhoneNumber && !isPhoneChanged && (
                <p className="text-xs text-emerald-600 mt-2 flex items-center gap-1.5">
                  <svg
                    className="h-3.5 w-3.5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Verified
                </p>
              )}
              {!isPasskeySession && isPhoneChanged && phoneNumber && (
                <>
                  <p className="text-xs text-amber-600 mt-2 flex items-center gap-1.5">
                    <svg
                      className="h-3.5 w-3.5"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                      aria-hidden="true"
                    >
                      <path
                        fillRule="evenodd"
                        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Verification required
                  </p>
                  <Button
                    type="button"
                    onClick={handleVerifyPhone}
                    disabled={sendPhoneOtpMutation.isPending}
                    className="mt-2 h-10"
                  >
                    {sendPhoneOtpMutation.isPending ? 'Sending...' : 'Send verification code'}
                  </Button>
                </>
              )}
              {!isPasskeySession && !savedPhoneNumber && !phoneNumber && (
                <p className="text-xs text-muted-foreground mt-1">
                  Add a phone number for account security
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Passkey Settings */}
        <PasskeySettings />

        {/* Linked Devices */}
        <DeviceList />
      </div>

      {/* OTP Verification Dialog */}
      <Dialog open={showVerifyDialog} onOpenChange={setShowVerifyDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Verify your phone number</DialogTitle>
            <DialogDescription>
              We sent a 6-digit verification code to {pendingPhone}. Enter it below to verify your
              phone.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <label htmlFor="otp" className="block text-sm font-medium mb-2">
                Verification code
              </label>
              <input
                ref={otpInputRef}
                id="otp"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={otpCode}
                onChange={(e) => {
                  setOtpCode(e.target.value.replace(/\D/g, ''))
                }}
                placeholder="123456"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm text-center text-2xl tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div className="flex gap-2">
              <Button
                type="button"
                onClick={handleVerifyOtp}
                disabled={verifyPhoneOtpMutation.isPending || otpCode.length !== 6}
                className="flex-1"
              >
                {verifyPhoneOtpMutation.isPending ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    Verifying...
                  </>
                ) : (
                  'Verify'
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={handleResendOtp}
                disabled={sendPhoneOtpMutation.isPending}
              >
                Resend
              </Button>
            </div>

            <p className="text-xs text-muted-foreground text-center">
              Didn't receive the code? Check your SMS messages or click Resend.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
