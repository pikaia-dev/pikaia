import { Outlet } from "react-router-dom"

import { AppSidebar } from "../components/app-sidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "../components/ui/sidebar"
import { PasskeyEnrollmentPrompt } from "../features/auth/components"

export default function AppLayout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
        </header>
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </SidebarInset>
      {/* Prompt user to add passkey if they don't have one */}
      <PasskeyEnrollmentPrompt />
    </SidebarProvider>
  )
}
