import { AdminPortalSSO } from "@stytch/react/b2b/adminPortal"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card"

// Style the Stytch Admin Portal to match the shadcn theme
const adminPortalStyles = {
  container: {
    backgroundColor: "transparent",
    borderColor: "transparent",
    borderRadius: "0",
    width: "100%",
  },
  colors: {
    primary: "hsl(var(--primary))",
    secondary: "hsl(var(--secondary))",
    success: "hsl(var(--success, 142 76% 36%))",
    error: "hsl(var(--destructive))",
  },
  buttons: {
    primary: {
      backgroundColor: "hsl(var(--primary))",
      borderColor: "hsl(var(--primary))",
      borderRadius: "calc(var(--radius) - 2px)",
      textColor: "hsl(var(--primary-foreground))",
    },
    secondary: {
      backgroundColor: "hsl(var(--secondary))",
      borderColor: "hsl(var(--border))",
      borderRadius: "calc(var(--radius) - 2px)",
      textColor: "hsl(var(--secondary-foreground))",
    },
  },
  inputs: {
    backgroundColor: "hsl(var(--background))",
    borderColor: "hsl(var(--input))",
    borderRadius: "calc(var(--radius) - 2px)",
    textColor: "hsl(var(--foreground))",
    placeholderColor: "hsl(var(--muted-foreground))",
  },
  fontFamily: "inherit",
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
            <CardTitle className="text-base">
              Single Sign-On (SSO)
            </CardTitle>
            <CardDescription>
              Allow members to sign in using your identity provider (Okta,
              Microsoft Entra, Google Workspace, etc.)
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
