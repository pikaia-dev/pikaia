import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStytchMemberSession } from '@stytch/react/b2b'

/**
 * Auth callback redirects to login page where StytchB2B handles everything.
 */
export default function AuthCallback() {
    const { session, isInitialized } = useStytchMemberSession()
    const navigate = useNavigate()

    useEffect(() => {
        if (!isInitialized) return

        if (session) {
            navigate('/dashboard', { replace: true })
        } else {
            const currentUrl = new URL(window.location.href)
            navigate(`/login${currentUrl.search}`, { replace: true })
        }
    }, [session, isInitialized, navigate])

    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground mx-auto"></div>
                <p className="mt-4 text-sm text-muted-foreground">Redirecting...</p>
            </div>
        </div>
    )
}

