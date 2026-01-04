import { useEffect, useRef,useState } from "react"
import { toast } from "sonner"

import { Button } from "../../components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog"
import { ImageUploader } from "../../components/ui/image-uploader"
import { LoadingSpinner } from "../../components/ui/loading-spinner"
import { PhoneNumberInput } from "../../components/ui/phone-number-input"
import { useApi } from "../../hooks/useApi"

// Delay before updating state after dialog close animation
const DIALOG_CLOSE_DELAY_MS = 150

export default function ProfileSettings() {
  const {
    getCurrentUser,
    updateProfile,
    sendPhoneOtp,
    verifyPhoneOtp,
    startEmailUpdate,
  } = useApi()
  const [name, setName] = useState("")
  const [savedName, setSavedName] = useState("")
  const [email, setEmail] = useState("")
  const [phoneNumber, setPhoneNumber] = useState("")
  const [savedPhoneNumber, setSavedPhoneNumber] = useState("")
  const [avatarUrl, setAvatarUrl] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Phone verification state
  const [showVerifyDialog, setShowVerifyDialog] = useState(false)
  const [otpCode, setOtpCode] = useState("")
  const [sendingOtp, setSendingOtp] = useState(false)
  const [verifyingOtp, setVerifyingOtp] = useState(false)
  const [pendingPhone, setPendingPhone] = useState("")
  const otpInputRef = useRef<HTMLInputElement>(null)

  // Email update state
  const [newEmail, setNewEmail] = useState("")
  const [sendingEmailUpdate, setSendingEmailUpdate] = useState(false)

  useEffect(() => {
    getCurrentUser()
      .then((data) => {
        setName(data.user.name)
        setSavedName(data.user.name)
        setEmail(data.user.email)
        setNewEmail(data.user.email) // Initialize newEmail with current email
        setPhoneNumber(data.user.phone_number || "")
        setSavedPhoneNumber(data.user.phone_number || "")
        setAvatarUrl(data.user.avatar_url || "")
      })
      .catch((err) => {
        toast.error(
          err instanceof Error ? err.message : "Failed to load profile"
        )
      })
      .finally(() => { setLoading(false); })
  }, [getCurrentUser])

  const handleSubmit = async () => {
    setSaving(true)

    try {
      await updateProfile({ name })
      setSavedName(name) // Update saved name on success
      toast.success("Name updated successfully")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update")
    } finally {
      setSaving(false)
    }
  }

  const isNameChanged = name !== savedName

  const isPhoneChanged = phoneNumber !== savedPhoneNumber

  const handleStartEmailUpdate = async () => {
    if (!newEmail || newEmail.toLowerCase() === email.toLowerCase()) return

    setSendingEmailUpdate(true)
    try {
      await startEmailUpdate(newEmail)
      toast.success(
        `Verification email sent to ${newEmail}. Check your inbox to complete the change.`
      )
      // Reset newEmail to current email (change won't take effect until verified)
      setNewEmail(email)
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to start email update"
      )
    } finally {
      setSendingEmailUpdate(false)
    }
  }

  const isEmailChanged = newEmail.toLowerCase() !== email.toLowerCase()

  const handleVerifyPhone = async () => {
    if (!phoneNumber) return

    setSendingOtp(true)
    try {
      await sendPhoneOtp(phoneNumber)
      setPendingPhone(phoneNumber)
      setOtpCode("")
      setShowVerifyDialog(true)
      toast.success("Verification code sent!")
      // Focus OTP input after dialog opens
      setTimeout(() => otpInputRef.current?.focus(), 100)
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to send verification code"
      )
    } finally {
      setSendingOtp(false)
    }
  }

  const handleVerifyOtp = async () => {
    if (!otpCode || otpCode.length !== 6) {
      toast.error("Please enter a 6-digit code")
      return
    }

    setVerifyingOtp(true)
    try {
      const updatedUser = await verifyPhoneOtp(pendingPhone, otpCode)
      // Close dialog first, then update state after animation
      setShowVerifyDialog(false)
      toast.success("Phone number verified and saved!")
      // Update phone state after dialog close animation
      setTimeout(() => {
        setPhoneNumber(updatedUser.phone_number)
        setSavedPhoneNumber(updatedUser.phone_number)
        setOtpCode("")
        setPendingPhone("")
      }, DIALOG_CLOSE_DELAY_MS)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verification failed")
    } finally {
      setVerifyingOtp(false)
    }
  }

  const handleResendOtp = async () => {
    setSendingOtp(true)
    try {
      await sendPhoneOtp(pendingPhone)
      setOtpCode("")
      toast.success("New verification code sent!")
      setTimeout(() => otpInputRef.current?.focus(), 100)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to resend code")
    } finally {
      setSendingOtp(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Profile</h1>
        <p className="text-muted-foreground">
          Manage your personal information
        </p>
      </div>

      <div className="space-y-6 max-w-lg">
        {/* Avatar Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Profile Picture</CardTitle>
            <CardDescription>
              Upload a photo to personalize your account
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ImageUploader
              type="avatar"
              value={avatarUrl}
              onChange={setAvatarUrl}
            />
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
                onChange={(e) => { setName(e.target.value); }}
                className="w-full h-10 px-3 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="Your name"
              />
              {isNameChanged && (
                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={saving}
                  className="mt-2 h-10"
                >
                  {saving ? "Saving..." : "Save name"}
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
                onChange={(e) => { setNewEmail(e.target.value); }}
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
                    If you signed in with Google, changing email will disconnect
                    that login method.
                  </p>
                  <Button
                    type="button"
                    onClick={handleStartEmailUpdate}
                    disabled={sendingEmailUpdate}
                    className="mt-2 h-10"
                  >
                    {sendingEmailUpdate
                      ? "Sending..."
                      : "Send verification link"}
                  </Button>
                </>
              )}
            </div>

            {/* Phone Number */}
            <div>
              <label className="block text-sm font-medium mb-1">
                Phone number
              </label>
              <PhoneNumberInput value={phoneNumber} onChange={setPhoneNumber} />
              {/* Show status based on current state */}
              {savedPhoneNumber && !isPhoneChanged && (
                <p className="text-xs text-emerald-600 mt-2 flex items-center gap-1.5">
                  <svg
                    className="h-3.5 w-3.5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
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
              {isPhoneChanged && phoneNumber && (
                <>
                  <p className="text-xs text-amber-600 mt-2 flex items-center gap-1.5">
                    <svg
                      className="h-3.5 w-3.5"
                      fill="currentColor"
                      viewBox="0 0 20 20"
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
                    disabled={sendingOtp}
                    className="mt-2 h-10"
                  >
                    {sendingOtp ? "Sending..." : "Send verification code"}
                  </Button>
                </>
              )}
              {!savedPhoneNumber && !phoneNumber && (
                <p className="text-xs text-muted-foreground mt-1">
                  Add a phone number for account security
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* OTP Verification Dialog */}
      <Dialog open={showVerifyDialog} onOpenChange={setShowVerifyDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Verify your phone number</DialogTitle>
            <DialogDescription>
              We sent a 6-digit verification code to {pendingPhone}. Enter it
              below to verify your phone.
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
                onChange={(e) => { setOtpCode(e.target.value.replace(/\D/g, "")); }}
                placeholder="123456"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm text-center text-2xl tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div className="flex gap-2">
              <Button
                type="button"
                onClick={handleVerifyOtp}
                disabled={verifyingOtp || otpCode.length !== 6}
                className="flex-1"
              >
                {verifyingOtp ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    Verifying...
                  </>
                ) : (
                  "Verify"
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={handleResendOtp}
                disabled={sendingOtp}
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
