import { useEffect, useState } from "react"
import { Bell, Clock, LogOut, Menu, Moon, ShieldAlert, Sun, Wifi, WifiOff } from "lucide-react"
import type { HealthResponse, MeResponse, Violation, ViolationListResponse } from "@/types"
import { Button } from "@/components/ui/button"
import type { RangeKey, TabKey } from "@/types/app"
import { formatClock, formatRelative, ROLE_LABEL, SECTOR_LABEL, TAB_TITLES, violationLabel } from "@/lib/domain"
import { ErrorState } from "@/shared/ErrorState"
import { SegmentedToggle } from "@/shared/SegmentedToggle"

interface Props {
  activeTab: TabKey
  range: RangeKey
  onRangeChange: (range: RangeKey) => void
  mobile: boolean
  sidebarOpen: boolean
  onOpenSidebar: () => void
  dark: boolean
  onToggleTheme: () => void
  user: MeResponse | undefined
  health: HealthResponse | undefined
  healthLoading: boolean
  healthError: boolean
  onRetryHealth: () => void
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

export function Topbar({ activeTab, range, onRangeChange, mobile, sidebarOpen, onOpenSidebar, dark, onToggleTheme, user, health, healthLoading, healthError, onRetryHealth, unseen, violations, violationsError, onRetryViolations, recentViolations, rangeLabel, ppeLabels, cameraName, now, onMarkSeen, onOpenFrame, onViewAllViolations, onLogout }: Props) {
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const userName = user?.username ?? "حساب Nexora"
  const roleLabel = user ? `${ROLE_LABEL[user.role] ?? user.role} · ${SECTOR_LABEL[user.sector] ?? ""}` : "مستخدم"
  const serverOk = health?.status === "ok" && !healthError
  const crumbs = [TAB_TITLES[activeTab]]

  useEffect(() => {
    if (!notificationsOpen) return
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setNotificationsOpen(false) }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [notificationsOpen])

  const toggleNotifications = () => {
    const nextOpen = !notificationsOpen
    setNotificationsOpen(nextOpen)
    if (nextOpen) onMarkSeen()
  }

  return (
    <header className="glass z-30 flex h-[68px] shrink-0 items-center justify-between gap-2 border-b border-border/50 px-3 sm:px-4 lg:px-7">
      <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
        {mobile && (
          <button type="button" aria-label="فتح قائمة التنقل" aria-expanded={sidebarOpen} aria-controls="app-sidebar" onClick={onOpenSidebar} className="tap-target -me-1 flex shrink-0 items-center justify-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground">
            <Menu className="size-5" />
          </button>
        )}
        <div className="min-w-0">
          <nav aria-label="مسار التنقل" className="flex items-center gap-1.5 truncate text-[10px] font-medium text-muted-foreground sm:text-[11px]">
            <span>Nexora</span><span aria-hidden="true">/</span><span>{crumbs[0]}</span>
          </nav>
          <h1 className="truncate text-base font-bold tracking-tight text-foreground sm:text-lg">{TAB_TITLES[activeTab]}</h1>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1 sm:gap-2 md:gap-3">
        <span className={`hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold sm:inline-flex ${serverOk ? "border-success/20 bg-success-light/65 text-success-foreground" : healthLoading ? "border-border bg-muted text-muted-foreground" : "border-destructive/20 bg-destructive-light text-destructive-foreground"}`}>
          {healthLoading ? <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground" /> : serverOk ? <Wifi className="size-3.5" /> : <WifiOff className="size-3.5" />}
          {healthLoading ? "فحص" : serverOk ? "الخادم متصل" : <button type="button" onClick={onRetryHealth} className="underline underline-offset-2">غير متصل</button>}
        </span>

        <SegmentedToggle className="hidden md:inline-grid" checked={range === "7d"} onChange={(value) => onRangeChange(value ? "7d" : "24h")} labelOn="7 أيام" labelOff="اليوم" ariaLabel="النطاق الزمني" />
        <button type="button" className="min-h-11 rounded-lg border border-border bg-card px-2.5 text-[11px] font-semibold text-muted-foreground md:hidden" aria-label="تغيير النطاق الزمني" onClick={() => onRangeChange(range === "24h" ? "7d" : "24h")}>{range === "24h" ? "24 ساعة" : "7 أيام"}</button>

        <span className="hidden items-center gap-1.5 text-xs tabular-nums text-muted-foreground lg:flex"><Clock className="size-3.5 opacity-70" /><time dateTime={new Date(now).toISOString()}>{formatClock(now)}</time></span>

        <Button type="button" size="icon" variant="ghost" aria-label={dark ? "التبديل إلى الوضع الفاتح" : "التبديل إلى الوضع الداكن"} onClick={onToggleTheme} className="tap-target rounded-xl hover:bg-muted">{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}</Button>

        <div className="relative">
          <Button type="button" size="icon" variant="ghost" aria-label={`التنبيهات${unseen ? `، ${unseen} جديد` : ""}`} aria-expanded={notificationsOpen} onClick={toggleNotifications} className="tap-target relative rounded-xl hover:bg-muted">
            <Bell className="size-4" />
            {unseen > 0 && <span className="absolute end-2 top-2 size-2 rounded-full bg-destructive ring-2 ring-background" />}
          </Button>
          {notificationsOpen && (
            <>
              <button type="button" aria-label="إغلاق قائمة التنبيهات" className="fixed inset-0 z-40 cursor-default" onClick={() => setNotificationsOpen(false)} />
              <div role="dialog" aria-label="آخر التنبيهات" className="card-premium absolute end-0 top-12 z-50 w-[min(360px,92vw)] overflow-hidden rounded-2xl border border-border bg-card p-2 shadow-floating">
                <div className="flex items-center justify-between gap-3 px-3 py-2">
                  <div className="flex items-center gap-2"><ShieldAlert className="size-4 text-destructive" /><p className="text-xs font-bold">آخر التنبيهات</p></div>
                  <span className="text-[10px] text-muted-foreground">{rangeLabel}</span>
                </div>
                {violationsError && !violations ? <div className="px-2 pb-2"><ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={onRetryViolations} /></div> : recentViolations.length === 0 ? (
                  <p className="px-3 py-4 text-sm text-muted-foreground">لا توجد تنبيهات جديدة في هذه الفترة.</p>
                ) : recentViolations.slice(0, 5).map((violation) => (
                  <button key={violation.id} type="button" onClick={() => { setNotificationsOpen(false); onOpenFrame(violation.frame_url) }} className="flex min-h-12 w-full items-center gap-3 rounded-xl px-3 py-2 text-start transition-colors hover:bg-muted/60">
                    <span className="size-2 shrink-0 rounded-full bg-destructive" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold">{violationLabel(violation.violation_type, ppeLabels)}</span>
                      <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">{cameraName(violation.camera_id)}</span>
                    </span>
                    <span className="shrink-0 text-[11px] text-muted-foreground">{formatRelative(violation.timestamp, now)}</span>
                  </button>
                ))}
                <button type="button" onClick={() => { setNotificationsOpen(false); onViewAllViolations() }} className="mt-1 min-h-11 w-full rounded-xl px-3 text-center text-xs font-bold text-primary hover:bg-primary-light">عرض السجل الكامل</button>
              </div>
            </>
          )}
        </div>

        <div className="hidden max-w-40 items-center gap-2 rounded-full border border-border/70 bg-card/75 py-1 ps-1 pe-3 sm:flex">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary-light text-xs font-bold text-primary" aria-hidden="true">{userName.charAt(0).toLocaleUpperCase()}</span>
          <span className="min-w-0"><span className="block truncate text-xs font-semibold">{userName}</span><span className="block truncate text-[10px] text-muted-foreground">{roleLabel}</span></span>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onLogout} aria-label="تسجيل الخروج" title="تسجيل الخروج" className="tap-target hidden rounded-xl text-muted-foreground hover:bg-destructive-light hover:text-destructive sm:inline-flex"><LogOut className="size-4" /></Button>
      </div>
    </header>
  )
}
