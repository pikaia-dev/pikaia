import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { StytchB2B, useStytchMemberSession } from '@stytch/react/b2b'
import { B2BProducts, AuthFlowType } from '@stytch/vanilla-js/b2b'

// Discovery config - let Stytch Dashboard handle redirect URLs
const config = {
    products: [B2BProducts.emailMagicLinks],
    sessionOptions: {
        sessionDurationMinutes: 60,
    },
    authFlowType: AuthFlowType.Discovery,
}

// Stytch styles aligned with shadcn/ui default theme (neutral/zinc)
const styles = {
    container: {
        width: '100%',
    },
    colors: {
        primary: '#18181b',      // zinc-900 - matches shadcn primary
        secondary: '#71717a',    // zinc-500 - muted text
        success: '#22c55e',      // green-500
        error: '#ef4444',        // red-500
    },
    buttons: {
        primary: {
            backgroundColor: '#18181b',  // zinc-900
            textColor: '#fafafa',        // zinc-50
            borderRadius: '6px',         // matches shadcn radius
        },
    },
    inputs: {
        borderColor: '#e4e4e7',  // zinc-200 - matches shadcn input border
        borderRadius: '6px',
    },
    fontFamily: 'inherit',      // Use app's font
}

export default function Login() {
    const navigate = useNavigate()
    const { session, isInitialized } = useStytchMemberSession()

    useEffect(() => {
        if (isInitialized && session) {
            navigate('/dashboard', { replace: true })
        }
    }, [session, isInitialized, navigate])

    if (!isInitialized || session) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground"></div>
            </div>
        )
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="w-full max-w-sm p-8">
                <div className="text-center mb-6">
                    <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
                    <p className="text-sm text-muted-foreground mt-2">
                        Enter your email to sign in to your account
                    </p>
                </div>
                <StytchB2B config={config} styles={styles} />
            </div>
        </div>
    )
}
