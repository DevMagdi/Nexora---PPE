import type { ReactNode } from "react"
import Sidebar, { type SidebarProps } from "@/layout/Sidebar"
import Topbar, { type TopbarProps } from "@/layout/Topbar"
import type { TabKey } from "@/types"

interface AppShellProps {
  tab: TabKey
  sidebarProps: SidebarProps
  topbarProps: TopbarProps
  children: ReactNode
}

export default function AppShell({ tab, sidebarProps, topbarProps, children }: AppShellProps) {
  return (
    <div className="flex min-h-dvh w-full bg-background text-foreground" dir="rtl" lang="ar">
      <Sidebar {...sidebarProps} />
      <main className="flex h-dvh min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar {...topbarProps} />
        <div key={tab} className="flex-1 animate-page-in overflow-y-auto p-5 lg:p-10">
          {children}
        </div>
      </main>
    </div>
  )
}
