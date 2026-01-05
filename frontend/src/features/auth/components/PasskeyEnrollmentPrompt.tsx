/**
 * Passkey Enrollment Prompt
 *
 * Shows a dialog prompting users to add a passkey after login
 * if they don't have one and their device supports WebAuthn.
 */

import { useEffect, useState } from "react"
import { Fingerprint } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

import {
    usePasskeys,
    useRegisterPasskey,
    isWebAuthnSupported,
} from "../hooks/usePasskeyAuth"

// LocalStorage key for tracking prompt dismissal
const PROMPT_DISMISSED_KEY = "passkey_prompt_dismissed"
const PROMPT_NEVER_ASK_KEY = "passkey_prompt_never_ask"

function hasSeenPromptThisSession(): boolean {
    if (typeof window === "undefined") return true
    return sessionStorage.getItem(PROMPT_DISMISSED_KEY) === "true"
}

function setPromptDismissedThisSession(): void {
    if (typeof window === "undefined") return
    sessionStorage.setItem(PROMPT_DISMISSED_KEY, "true")
}

function hasNeverAskAgain(): boolean {
    if (typeof window === "undefined") return true
    return localStorage.getItem(PROMPT_NEVER_ASK_KEY) === "true"
}

function setNeverAskAgain(): void {
    if (typeof window === "undefined") return
    localStorage.setItem(PROMPT_NEVER_ASK_KEY, "true")
}

export function PasskeyEnrollmentPrompt() {
    const [isOpen, setIsOpen] = useState(false)
    const [isRegistering, setIsRegistering] = useState(false)
    const [passkeyName, setPasskeyName] = useState("")

    const { data: passkeysData, isLoading: isLoadingPasskeys } = usePasskeys()
    const registerMutation = useRegisterPasskey()

    const passkeys = passkeysData?.passkeys ?? []

    // Check if we should show the prompt
    useEffect(() => {
        // Don't show if:
        // - Still loading passkeys
        // - User already has passkeys
        // - Device doesn't support WebAuthn
        // - User already dismissed this session
        // - User selected "don't ask again"
        if (isLoadingPasskeys) return
        if (passkeys.length > 0) return
        if (!isWebAuthnSupported()) return
        if (hasSeenPromptThisSession()) return
        if (hasNeverAskAgain()) return

        // Small delay to let the page settle after login
        const timer = setTimeout(() => {
            setIsOpen(true)
        }, 1000)

        return () => clearTimeout(timer)
    }, [isLoadingPasskeys, passkeys.length])

    const handleDismiss = () => {
        setPromptDismissedThisSession()
        setIsOpen(false)
    }

    const handleNeverAsk = () => {
        setNeverAskAgain()
        setPromptDismissedThisSession()
        setIsOpen(false)
    }

    const handleRegister = async () => {
        const name = passkeyName.trim() || "My Passkey"
        setIsRegistering(true)

        try {
            await registerMutation.mutateAsync(name)
            toast.success("Passkey added! You can now sign in without a password.")
            setPromptDismissedThisSession()
            setIsOpen(false)
        } catch (error) {
            if (error instanceof Error) {
                // User cancelled or error
                if (!error.message.includes("cancelled") && !error.message.includes("AbortError")) {
                    toast.error(error.message)
                }
            }
        } finally {
            setIsRegistering(false)
        }
    }

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && handleDismiss()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                        <Fingerprint className="h-6 w-6 text-primary" />
                    </div>
                    <DialogTitle className="text-center">
                        Enable passwordless login?
                    </DialogTitle>
                    <DialogDescription className="text-center">
                        Add a passkey to sign in faster and more securely using Face ID,
                        Touch ID, or your device PIN.
                    </DialogDescription>
                </DialogHeader>

                {isRegistering ? (
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="passkey-name">Name your passkey</Label>
                            <Input
                                id="passkey-name"
                                placeholder="e.g., MacBook Pro"
                                value={passkeyName}
                                onChange={(e) => setPasskeyName(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                        void handleRegister()
                                    }
                                }}
                                autoFocus
                            />
                            <p className="text-xs text-muted-foreground">
                                This helps you identify your passkey later.
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="py-4">
                        <ul className="space-y-2 text-sm text-muted-foreground">
                            <li className="flex items-start gap-2">
                                <span className="text-primary">✓</span>
                                <span>No more passwords to remember</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary">✓</span>
                                <span>Stronger security than passwords</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary">✓</span>
                                <span>Works across your devices</span>
                            </li>
                        </ul>
                    </div>
                )}

                <DialogFooter className="flex-col gap-2 sm:flex-col">
                    {isRegistering ? (
                        <>
                            <Button
                                onClick={() => void handleRegister()}
                                disabled={registerMutation.isPending}
                                className="w-full"
                            >
                                {registerMutation.isPending ? "Adding..." : "Add Passkey"}
                            </Button>
                            <Button
                                variant="ghost"
                                onClick={() => setIsRegistering(false)}
                                className="w-full"
                            >
                                Back
                            </Button>
                        </>
                    ) : (
                        <>
                            <Button
                                onClick={() => setIsRegistering(true)}
                                className="w-full"
                            >
                                Add Passkey
                            </Button>
                            <Button
                                variant="ghost"
                                onClick={handleDismiss}
                                className="w-full"
                            >
                                Maybe Later
                            </Button>
                            <button
                                type="button"
                                onClick={handleNeverAsk}
                                className="text-xs text-muted-foreground hover:text-foreground"
                            >
                                Don't ask again
                            </button>
                        </>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
