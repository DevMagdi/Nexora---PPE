import { useEffect, useState } from "react"
import type { ReactNode } from "react"
import type { HealthResponse, MeResponse, Violation, ViolationListResponse } from "@/types"
import type { RangeKey, TabKey } from "@/types/app"
import { useMediaQuery } from "@/hooks/useMediaQuery"
import { Sidebar } from "@/layout/Sidebar"
import { Topbar } from "@/layout/Topbar"

interface Props {
  children: ReactNode
  activeTab: TabKey
  onTabChange: (tab: TabKey) => void
  range: RangeKey
  onRangeChange: (range: RangeKey) => void
  dark: boolean
  onToggleTheme: () => void
  user: MeResponse | undefined
  health: HealthResponse | undefined
  healthLoading: boolean
  healthError: boolean
  onRetryHealth: () => void
  cameraCount: number
  runningCount: number
  unseen: number
  violations: ViolationListResponse | undefined
  violationsError: boolean
  onRetryViolations: () => void
  recentViolations: Violation[]
  rangeLabel: string
  ppeLabels: Map<string, string>
  cameraName: (id: number) => string
  now: number
  onMarkSeen: () => void
  onOpenFrame: (url?: string | null) => void
  onViewAllViolations: () => void
  onLogout: () => void
}

export function AppShell({ children, activeTab, onTabChange, range, onRangeChange, dark, onToggleTheme, user, health, healthLoading, healthError, onRetryHealth, cameraCount, runningCount, unseen, violations, violationsError, onRetryViolations, recentViolations, rangeLabel, ppeLabels, cameraName, now, onMarkSeen, onOpenFrame, onViewAllViolations, onLogout }: Props) {
  const mobile = useMediaQuery("(max-width: 1023.98px)")
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    if (!sidebarOpen) return
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setSidebarOpen(false) }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [sidebarOpen])

  return (
    <div className="flex min-h-dvh w-full bg-background text-foreground" dir="rtl" lang="ar">
      <Sidebar
        activeTab={activeTab}
        onTabChange={(nextTab) => { setSidebarOpen(false); onTabChange(nextTab) }}
        mobile={mobile}
        open={sidebarOpen}
        dark={dark}
        user={user}
        health={health}
        healthLoading={healthLoading}
        healthError={healthError}
        onRetryHealth={onRetryHealth}
        cameraCount={cameraCount}
        runningCount={runningCount}
        onLogout={onLogout}
        onClose={() => setSidebarOpen(false)}
      />
      {mobile && sidebarOpen && <button type="button" aria-label="إغلاق القائمة" className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[2px]" onClick={() => setSidebarOpen(false)} />}

      <main className="flex h-dvh min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar
          activeTab={activeTab}
          range={range}
          onRangeChange={onRangeChange}
          mobile={mobile}
          sidebarOpen={sidebarOpen}
          onOpenSidebar={() => setSidebarOpen(true)}
          dark={dark}
          onToggleTheme={onToggleTheme}
          user={user}
          health={health}
          healthLoading={healthLoading}
          healthError={healthError}
          onRetryHealth={onRetryHealth}
          unseen={unseen}
          violations={violations}
          violationsError={violationsError}
          onRetryViolations={onRetryViolations}
          recentViolations={recentViolations}
          rangeLabel={rangeLabel}
          ppeLabels={ppeLabels}
          cameraName={cameraName}
          now={now}
          onMarkSeen={onMarkSeen}
          onOpenFrame={onOpenFrame}
          onViewAllViolations={onViewAllViolations}
          onLogout={onLogout}
        />
        <div key={activeTab} className="flex-1 animate-page-in overflow-y-auto overscroll-contain p-4 sm:p-5 lg:p-7 2xl:p-9">
          {children}
        </div>
      </main>
    </div>
  )
}
