/**
 * Passkey settings component for managing user's passkeys.
 *
 * Allows users to register new passkeys and manage existing ones.
 */

import { formatDistanceToNow } from "date-fns"
import { AlertCircle, Key, Plus, Shield, Smartphone, Trash2 } from "lucide-react"
import { toast } from "sonner"

import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    isWebAuthnSupported,
    useDeletePasskey,
    usePasskeys,
    useRegisterPasskey,
} from "@/features/auth/hooks/usePasskeyAuth"
import { generatePasskeyName } from "@/features/auth/utils"

export function PasskeySettings() {
    const { data: passkeysData, isLoading: isLoadingPasskeys } = usePasskeys()
    const registerMutation = useRegisterPasskey()
    const deleteMutation = useDeletePasskey()

    const passkeys = passkeysData?.passkeys ?? []
    const isSupported = isWebAuthnSupported()

    const handleRegister = async () => {
        const name = generatePasskeyName()

        try {
            await registerMutation.mutateAsync(name)
            toast.success("Passkey registered successfully.")
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Failed to register passkey."
            )
        }
    }

    const handleDelete = async (passkeyId: number, passkeyNameToDelete: string) => {
        try {
            await deleteMutation.mutateAsync(passkeyId)
            toast.success(`"${passkeyNameToDelete}" has been removed.`)
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Failed to delete passkey."
            )
        }
    }

    if (!isSupported) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Key className="h-5 w-5" />
                        Passkeys
                    </CardTitle>
                    <CardDescription>
                        Sign in without a password using Face ID, Touch ID, or your device
                        PIN.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                        <AlertCircle className="h-5 w-5 flex-shrink-0" />
                        <p className="text-sm">
                            Passkeys are not supported in this browser. Try using Chrome,
                            Safari, or Edge on a recent version.
                        </p>
                    </div>
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader>
                <div className="flex items-start justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <Key className="h-5 w-5" />
                            Passkeys
                        </CardTitle>
                        <CardDescription className="mt-1">
                            Sign in without a password using Face ID, Touch ID, or your device
                            PIN.
                        </CardDescription>
                    </div>
                    {passkeys.length > 0 && (
                        <Button
                            size="sm"
                            className="gap-1.5"
                            onClick={() => void handleRegister()}
                            disabled={registerMutation.isPending}
                        >
                            <Plus className="h-4 w-4" />
                            {registerMutation.isPending ? "Adding..." : "Add Passkey"}
                        </Button>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                {isLoadingPasskeys ? (
                    <div className="flex items-center justify-center py-8 text-muted-foreground">
                        Loading passkeys...
                    </div>
                ) : passkeys.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                        <Shield className="mb-3 h-12 w-12 text-muted-foreground/50" />
                        <p className="text-sm text-muted-foreground">
                            No passkeys registered yet.
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            Add a passkey to sign in more securely without a password.
                        </p>
                        <Button
                            size="sm"
                            className="mt-4 gap-1.5"
                            onClick={() => void handleRegister()}
                            disabled={registerMutation.isPending}
                        >
                            <Plus className="h-4 w-4" />
                            {registerMutation.isPending ? "Adding..." : "Add Passkey"}
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {passkeys.map((passkey) => (
                            <div
                                key={passkey.id}
                                className="group relative overflow-hidden rounded-xl border bg-card transition-all hover:shadow-md hover:border-primary/20"
                            >
                                {/* Subtle gradient background */}
                                <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.03] via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                                <div className="relative flex items-center justify-between p-5">
                                    <div className="flex items-center gap-4 flex-1 min-w-0">
                                        {/* Icon with gradient background */}
                                        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 ring-1 ring-primary/10 transition-all group-hover:scale-105 group-hover:ring-primary/20 flex-shrink-0">
                                            <Smartphone className="h-6 w-6 text-primary" />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <p className="font-semibold text-base truncate">{passkey.name}</p>
                                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5 text-sm text-muted-foreground">
                                                <span className="flex items-center gap-1.5">
                                                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                    </svg>
                                                    Added {formatDistanceToNow(new Date(passkey.created_at), { addSuffix: true })}
                                                </span>
                                                {passkey.last_used_at && (
                                                    <span className="flex items-center gap-1.5">
                                                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                        </svg>
                                                        Last used {formatDistanceToNow(new Date(passkey.last_used_at), { addSuffix: true })}
                                                    </span>
                                                )}
                                                {passkey.backup_state && (
                                                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 text-xs font-medium ring-1 ring-emerald-600/20">
                                                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                        </svg>
                                                        Synced
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    <AlertDialog>
                                        <AlertDialogTrigger asChild>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-all flex-shrink-0"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                                <span className="sr-only">Delete passkey</span>
                                            </Button>
                                        </AlertDialogTrigger>
                                        <AlertDialogContent>
                                            <AlertDialogHeader>
                                                <AlertDialogTitle>Delete passkey?</AlertDialogTitle>
                                                <AlertDialogDescription>
                                                    This will remove "{passkey.name}" from your account. You
                                                    won't be able to sign in with this passkey anymore.
                                                </AlertDialogDescription>
                                            </AlertDialogHeader>
                                            <AlertDialogFooter>
                                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                <AlertDialogAction
                                                    onClick={() => void handleDelete(passkey.id, passkey.name)}
                                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                                >
                                                    {deleteMutation.isPending ? "Deleting..." : "Delete"}
                                                </AlertDialogAction>
                                            </AlertDialogFooter>
                                        </AlertDialogContent>
                                    </AlertDialog>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
