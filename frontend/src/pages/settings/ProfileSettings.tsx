import { useState, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { useApi } from '../../hooks/useApi'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { LoadingSpinner } from '../../components/ui/loading-spinner'
import { ImageUploader } from '../../components/ui/image-uploader'
import { PhoneNumberInput } from '../../components/ui/phone-number-input'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '../../components/ui/dialog'

export default function ProfileSettings() {
    const { getCurrentUser, updateProfile, sendPhoneOtp, verifyPhoneOtp } = useApi()
    const [name, setName] = useState('')
    const [email, setEmail] = useState('')
    const [phoneNumber, setPhoneNumber] = useState('')
    const [savedPhoneNumber, setSavedPhoneNumber] = useState('')
    const [avatarUrl, setAvatarUrl] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

    // Phone verification state
    const [showVerifyDialog, setShowVerifyDialog] = useState(false)
    const [otpCode, setOtpCode] = useState('')
    const [sendingOtp, setSendingOtp] = useState(false)
    const [verifyingOtp, setVerifyingOtp] = useState(false)
    const [pendingPhone, setPendingPhone] = useState('')
    const otpInputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        getCurrentUser()
            .then((data) => {
                setName(data.user.name)
                setEmail(data.user.email)
                setPhoneNumber(data.user.phone_number || '')
                setSavedPhoneNumber(data.user.phone_number || '')
                setAvatarUrl(data.user.avatar_url || '')
            })
            .catch((err) => {
                toast.error(err instanceof Error ? err.message : 'Failed to load profile')
            })
            .finally(() => setLoading(false))
    }, [getCurrentUser])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setSaving(true)

        try {
            await updateProfile({ name })
            toast.success('Profile updated successfully')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to update')
        } finally {
            setSaving(false)
        }
    }

    const isPhoneChanged = phoneNumber !== savedPhoneNumber

    const handleVerifyPhone = async () => {
        if (!phoneNumber) return

        setSendingOtp(true)
        try {
            await sendPhoneOtp(phoneNumber)
            setPendingPhone(phoneNumber)
            setOtpCode('')
            setShowVerifyDialog(true)
            toast.success('Verification code sent!')
            // Focus OTP input after dialog opens
            setTimeout(() => otpInputRef.current?.focus(), 100)
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to send verification code')
        } finally {
            setSendingOtp(false)
        }
    }

    const handleVerifyOtp = async () => {
        if (!otpCode || otpCode.length !== 6) {
            toast.error('Please enter a 6-digit code')
            return
        }

        setVerifyingOtp(true)
        try {
            const updatedUser = await verifyPhoneOtp(pendingPhone, otpCode)
            setPhoneNumber(updatedUser.phone_number)
            setSavedPhoneNumber(updatedUser.phone_number)
            setShowVerifyDialog(false)
            setOtpCode('')
            toast.success('Phone number verified and saved!')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Verification failed')
        } finally {
            setVerifyingOtp(false)
        }
    }

    const handleResendOtp = async () => {
        setSendingOtp(true)
        try {
            await sendPhoneOtp(pendingPhone)
            setOtpCode('')
            toast.success('New verification code sent!')
            otpInputRef.current?.focus()
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to resend code')
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
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label htmlFor="email" className="block text-sm font-medium mb-1">
                                    Email
                                </label>
                                <input
                                    id="email"
                                    type="email"
                                    value={email}
                                    disabled
                                    className="w-full px-3 py-2 border border-border rounded-md bg-muted text-muted-foreground text-sm"
                                />
                                <p className="text-xs text-muted-foreground mt-1">
                                    Email is managed by Stytch and cannot be changed here
                                </p>
                            </div>

                            <div>
                                <label htmlFor="name" className="block text-sm font-medium mb-1">
                                    Display name
                                </label>
                                <input
                                    id="name"
                                    type="text"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="Your name"
                                />
                            </div>

                            <Button type="submit" disabled={saving}>
                                {saving ? 'Saving...' : 'Save changes'}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {/* Phone Number Card - Separate because it requires verification */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Phone Number</CardTitle>
                        <CardDescription>
                            Used for account security and notifications.
                            Requires SMS verification.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div>
                            <PhoneNumberInput
                                value={phoneNumber}
                                onChange={setPhoneNumber}
                            />
                            {savedPhoneNumber && (
                                <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                                    <span>✓</span>
                                    Verified: {savedPhoneNumber}
                                </p>
                            )}
                        </div>

                        {isPhoneChanged && phoneNumber && (
                            <Button
                                type="button"
                                onClick={handleVerifyPhone}
                                disabled={sendingOtp}
                            >
                                {sendingOtp ? (
                                    <>
                                        <LoadingSpinner size="sm" className="mr-2" />
                                        Sending code...
                                    </>
                                ) : (
                                    'Verify phone number'
                                )}
                            </Button>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* OTP Verification Dialog */}
            <Dialog open={showVerifyDialog} onOpenChange={setShowVerifyDialog}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Verify your phone number</DialogTitle>
                        <DialogDescription>
                            We sent a 6-digit verification code to {pendingPhone}.
                            Enter it below to verify your phone.
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
                                maxLength={6}
                                value={otpCode}
                                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
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
                                    'Verify'
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
