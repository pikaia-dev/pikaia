import { AdminPortalSSO } from '@stytch/react/b2b/adminPortal'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

// Style the Stytch Admin Portal to match the shadcn theme
// Note: Stytch doesn't resolve CSS variables, so we use concrete color values
const adminPortalStyles = {
  container: {
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    borderRadius: '0',
    width: '100%',
  },
  colors: {
    primary: '#171717',
    secondary: '#fafafa',
    success: '#22c55e',
    error: '#ef4444',
  },
  buttons: {
    primary: {
      backgroundColor: '#171717',
      borderColor: '#171717',
      borderRadius: '0.375rem',
      textColor: '#fafafa',
    },
    secondary: {
      backgroundColor: '#fafafa',
      borderColor: '#d4d4d4',
      borderRadius: '0.375rem',
      textColor: '#171717',
    },
  },
  inputs: {
    backgroundColor: '#ffffff',
    borderColor: '#a3a3a3',
    borderRadius: '0.375rem',
    textColor: '#171717',
    placeholderColor: '#737373',
  },
  fontFamily: 'inherit',
}

export default function SecuritySettings() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Security</h1>
        <p className="text-muted-foreground">
          Configure enterprise authentication and security settings
        </p>
      </div>

      <div className="space-y-6 max-w-2xl">
        {/* SSO Configuration Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Single Sign-On (SSO)</CardTitle>
            <CardDescription>
              Allow members to sign in using your identity provider (Okta, Microsoft Entra, Google
              Workspace, etc.)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AdminPortalSSO styles={adminPortalStyles} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
