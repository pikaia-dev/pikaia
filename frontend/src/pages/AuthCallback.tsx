import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStytchMemberSession } from '@stytch/react/b2b'

/**
 * Auth callback simply redirects to login page where StytchB2B handles everything.
 * This ensures a single StytchB2B instance handles the full flow.
 */
export default function AuthCallback() {
    const { session, isInitialized } = useStytchMemberSession()
    const navigate = useNavigate()

    useEffect(() => {
        if (!isInitialized) return

        if (session) {
            // Already have a session, go to dashboard
            navigate('/dashboard', { replace: true })
        } else {
            // Redirect to login with the token params preserved
            // StytchB2B on login page will handle the token authentication
            const currentUrl = new URL(window.location.href)
            navigate(`/login${currentUrl.search}`, { replace: true })
        }
    }, [session, isInitialized, navigate])

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50">
            <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
                <p className="mt-4 text-slate-600">Redirecting...</p>
            </div>
        </div>
    )
}
