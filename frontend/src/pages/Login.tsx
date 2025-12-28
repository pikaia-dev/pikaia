import { useNavigate } from 'react-router-dom'
import { StytchB2B } from '@stytch/react/b2b'
import { B2BProducts, AuthFlowType, StytchEventType } from '@stytch/vanilla-js/b2b'

// Discovery config - let Stytch Dashboard handle redirect URLs
const config = {
    products: [B2BProducts.emailMagicLinks],
    sessionOptions: {
        sessionDurationMinutes: 60, // Match Stytch default max
    },
    authFlowType: AuthFlowType.Discovery,
}

const styles = {
    container: {
        width: '400px',
    },
    colors: {
        primary: '#0f172a',
        secondary: '#64748b',
        success: '#22c55e',
        error: '#ef4444',
    },
    buttons: {
        primary: {
            backgroundColor: '#0f172a',
            textColor: '#ffffff',
            borderRadius: '8px',
        },
    },
    inputs: {
        borderRadius: '8px',
    },
}

export default function Login() {
    const navigate = useNavigate()

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50">
            <div className="w-full max-w-md p-8">
                <div className="text-center mb-8">
                    <h1 className="text-2xl font-bold text-slate-900">Welcome</h1>
                    <p className="text-slate-600 mt-2">Sign in to continue</p>
                </div>
                <StytchB2B
                    config={config}
                    styles={styles}
                    callbacks={{
                        onEvent: (event) => {
                            if (event.type === StytchEventType.AuthenticateFlowComplete) {
                                navigate('/dashboard', { replace: true })
                            }
                        },
                    }}
                />
            </div>
        </div>
    )
}
