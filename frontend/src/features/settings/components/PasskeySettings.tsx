/**
 * Passkey settings component for managing user's passkeys.
 *
 * Allows users to register new passkeys and manage existing ones.
 */

import { formatDistanceToNow } from "date-fns"
import { AlertCircle,Key, Plus, Shield, Smartphone, Trash2 } from "lucide-react"
import { useState } from "react"
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
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    isWebAuthnSupported,
    useDeletePasskey,
    usePasskeys,
    useRegisterPasskey,
} from "@/features/auth/hooks/usePasskeyAuth"

export function PasskeySettings() {
    const [isDialogOpen, setIsDialogOpen] = useState(false)
    const [passkeyName, setPasskeyName] = useState("")

    const { data: passkeysData, isLoading: isLoadingPasskeys } = usePasskeys()
    const registerMutation = useRegisterPasskey()
    const deleteMutation = useDeletePasskey()

    const passkeys = passkeysData?.passkeys ?? []
    const isSupported = isWebAuthnSupported()

    const handleRegister = async () => {
        if (!passkeyName.trim()) {
            toast.error("Please enter a name for your passkey.")
            return
        }

        try {
            await registerMutation.mutateAsync(passkeyName.trim())
            toast.success("Passkey registered successfully.")
            setIsDialogOpen(false)
            setPasskeyName("")
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
                    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                        <DialogTrigger asChild>
                            <Button size="sm" className="gap-1.5">
                                <Plus className="h-4 w-4" />
                                Add Passkey
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Register a new passkey</DialogTitle>
                                <DialogDescription>
                                    Give your passkey a name to help you identify it later, like
                                    "MacBook Pro" or "iPhone 15".
                                </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <Label htmlFor="passkey-name">Passkey name</Label>
                                    <Input
                                        id="passkey-name"
                                        placeholder="e.g., MacBook Pro"
                                        value={passkeyName}
                                        onChange={(e) => { setPasskeyName(e.target.value); }}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter") {
                                                void handleRegister()
                                            }
                                        }}
                                    />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button
                                    variant="outline"
                                    onClick={() => {
                                        setIsDialogOpen(false)
                                        setPasskeyName("")
                                    }}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    onClick={() => void handleRegister()}
                                    disabled={registerMutation.isPending}
                                >
                                    {registerMutation.isPending ? "Registering..." : "Continue"}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
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
                    </div>
                ) : (
                    <div className="space-y-3">
                        {passkeys.map((passkey) => (
                            <div
                                key={passkey.id}
                                className="flex items-center justify-between rounded-lg border p-4"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                                        <Smartphone className="h-5 w-5 text-primary" />
                                    </div>
                                    <div>
                                        <p className="font-medium">{passkey.name}</p>
                                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                            <span>
                                                Added{" "}
                                                {formatDistanceToNow(new Date(passkey.created_at), {
                                                    addSuffix: true,
                                                })}
                                            </span>
                                            {passkey.last_used_at && (
                                                <>
                                                    <span>•</span>
                                                    <span>
                                                        Last used{" "}
                                                        {formatDistanceToNow(
                                                            new Date(passkey.last_used_at),
                                                            { addSuffix: true }
                                                        )}
                                                    </span>
                                                </>
                                            )}
                                            {passkey.backup_state && (
                                                <>
                                                    <span>•</span>
                                                    <span className="text-green-600 dark:text-green-400">
                                                        Synced
                                                    </span>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <AlertDialog>
                                    <AlertDialogTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
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
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
