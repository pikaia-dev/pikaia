import { MailIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

interface CheckEmailScreenProps {
    email: string
    onBack: () => void
}

export function CheckEmailScreen({ email, onBack }: CheckEmailScreenProps) {
    return (
        <div className="text-center space-y-6">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <MailIcon className="h-6 w-6 text-muted-foreground" />
            </div>

            <div className="space-y-2">
                <h2 className="text-xl font-semibold">Check your email</h2>
                <p className="text-sm text-muted-foreground">
                    We sent a sign-in link to{" "}
                    <span className="font-medium text-foreground">{email}</span>
                </p>
            </div>

            <p className="text-xs text-muted-foreground">
                Click the link in the email to sign in. If you don&apos;t see it, check
                your spam folder.
            </p>

            <Button variant="ghost" onClick={onBack} className="text-sm">
                Use a different email
            </Button>
        </div>
    )
}
