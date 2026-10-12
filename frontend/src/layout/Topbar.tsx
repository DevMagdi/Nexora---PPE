import { Bell, Clock, LogOut, Menu, Moon, ShieldCheck, Sun } from "lucide-react"
import { Button } from "@/components/ui/button"
import { formatClock, formatRelative, TAB_TITLES, violationLabel } from "@/lib/formatters"
import ErrorState from "@/shared/ErrorState"
import LiveDot from "@/shared/LiveDot"
import SegToggle from "@/shared/SegToggle"
import type { RangeKey, TabKey, Violation } from "@/types"

export interface TopbarProps {
  tab: TabKey
  crumbs: string[]
  isMobile: boolean
  sidebarOpen: boolean
  onOpenMobile: () => void
  range: RangeKey
  onRangeChange: (next: RangeKey) => void
  rangeLabel: string
  now: number
  dark: boolean
  onToggleDark: () => void
  unseenCount: number
  bellOpen: boolean
  onToggleBell: () => void
  onCloseBell: () => void
  overviewError: boolean
  hasOverviewRaw: boolean
  onRetryOverview: () => void
  overviewList: Violation[]
  ppeLabels: Map<string, string>
  onOpenFrame: (url?: string | null) => void
  onGoViolations: () => void
  displayName: string
  displayRole?: string
  serverOk?: boolean
  runningCount?: number
  onLogout?: () => void
}

export default function Topbar({
  tab,
  crumbs,
  isMobile,
  sidebarOpen,
  onOpenMobile,
  range,
  onRangeChange,
  rangeLabel,
  now,
  dark,
  onToggleDark,
  unseenCount,
  bellOpen,
  onToggleBell,
  onCloseBell,
  overviewError,
  hasOverviewRaw,
  onRetryOverview,
  overviewList,
  ppeLabels,
  onOpenFrame,
  onGoViolations,
  displayName,
  displayRole,
  serverOk = true,
  runningCount = 0,
  onLogout,
}: TopbarProps) {
  return (
    <header className="glass z-30 flex h-16 shrink-0 items-center justify-between gap-3 px-4 lg:px-8">
      <div className="flex min-w-0 items-center gap-3">
        {isMobile && (
          <button
            type="button"
            aria-label="فتح القائمة"
            aria-expanded={sidebarOpen}
            aria-controls="app-sidebar"
            onClick={onOpenMobile}
            className="-me-1 flex size-11 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Menu className="size-5" />
          </button>
        )}
        <div className="min-w-0">
          <nav
            aria-label="مسار التنقل"
            className="flex items-center gap-1.5 truncate text-[11px] font-medium text-muted-foreground"
          >
            <span className="font-semibold text-primary">Nexora</span>
            {crumbs.map((c) => (
              <span key={c} className="flex items-center gap-1.5">
                <span aria-hidden="true" className="opacity-50">
                  /
                </span>
                <span className="truncate">{c}</span>
              </span>
            ))}
          </nav>
          <h1 className="truncate text-lg font-bold tracking-tight lg:text-xl">{TAB_TITLES[tab]}</h1>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        {/* Live System Status Pill */}
        <div
          className={`hidden items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold xl:inline-flex ${
            serverOk
              ? "border-success/25 bg-success-light text-success-foreground"
              : "border-destructive/25 bg-destructive-light text-destructive-foreground"
          }`}
        >
          <LiveDot tone={serverOk ? "success" : "destructive"} active={serverOk} />
          <span>
            {serverOk
              ? runningCount > 0
                ? `متصل · ${runningCount} كاميرا نشطة`
                : "النظام متصل"
              : "انقطاع الاتصال بالخادم"}
          </span>
        </div>

        <SegToggle
          checked={range === "7d"}
          onChange={(v) => onRangeChange(v ? "7d" : "24h")}
          labelOn="7 أيام"
          labelOff="اليوم"
        />

        <div className="hidden h-5 w-px bg-border/70 md:block" />

        <div className="hidden items-center gap-1.5 text-xs font-semibold tabular-nums text-muted-foreground md:flex">
          <Clock className="size-3.5 opacity-70" />
          <time dateTime={new Date(now).toISOString()}>{formatClock(now)}</time>
        </div>

        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label={dark ? "التبديل إلى الوضع الفاتح" : "التبديل إلى الوضع الداكن"}
          onClick={onToggleDark}
          className="size-10 rounded-xl hover:bg-muted"
        >
          {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>

        <div className="relative">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            aria-label={`التنبيهات${unseenCount ? ` (${unseenCount} جديد)` : ""}`}
            aria-expanded={bellOpen}
            onClick={onToggleBell}
            className="relative size-10 rounded-xl hover:bg-muted"
          >
            <Bell className="size-4" />
            {unseenCount > 0 && (
              <span className="absolute right-2 top-2 size-2 animate-pulse rounded-full bg-destructive ring-2 ring-background" />
            )}
          </Button>

          {bellOpen && (
            <>
              <button
                type="button"
                aria-label="إغلاق التنبيهات"
                className="fixed inset-0 z-40 cursor-default"
                onClick={onCloseBell}
              />
              <div className="surface-floating absolute left-0 top-12 z-50 w-80 max-w-[90vw] animate-fade-in overflow-hidden p-2">
                <div className="flex items-center justify-between border-b border-border/50 px-3 py-2">
                  <p className="text-xs font-bold text-foreground">آخر التنبيهات</p>
                  <span className="text-[11px] font-medium text-muted-foreground">{rangeLabel}</span>
                </div>

                {overviewError && !hasOverviewRaw ? (
                  <div className="px-3 pb-3 pt-2">
                    <ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={onRetryOverview} />
                  </div>
                ) : overviewList.length === 0 ? (
                  <div className="flex flex-col items-center gap-1.5 px-3 py-6 text-center">
                    <ShieldCheck className="size-6 text-success" />
                    <p className="text-xs font-semibold text-foreground">لا توجد تنبيهات</p>
                    <p className="text-[11px] text-muted-foreground">
                      لم تُسجّل أي مخالفة خلال {rangeLabel}
                    </p>
                  </div>
                ) : (
                  <div className="mt-1 space-y-0.5">
                    {overviewList.slice(0, 5).map((v) => (
                      <button
                        key={v.id}
                        type="button"
                        onClick={() => {
                          onCloseBell()
                          onOpenFrame(v.frame_url)
                        }}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-start transition-colors hover:bg-muted/60"
                      >
                        <span
                          className={`size-2 shrink-0 rounded-full ${
                            v.is_resolved ? "bg-muted-foreground/40" : "bg-destructive"
                          }`}
                        />
                        <span className="flex-1 truncate text-xs font-bold text-foreground">
                          {violationLabel(v.violation_type, ppeLabels)}
                        </span>
                        <span className="shrink-0 text-[11px] text-muted-foreground">
                          {formatRelative(v.timestamp, now)}
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => {
                    onCloseBell()
                    onGoViolations()
                  }}
                  className="mt-1.5 w-full rounded-xl bg-primary-light px-3 py-2 text-center text-xs font-bold text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
                >
                  عرض السجل الكامل
                </button>
              </div>
            </>
          )}
        </div>

        {/* User / Role Chip */}
        <div className="hidden items-center gap-2.5 rounded-xl border border-border/70 bg-card/80 py-1 pe-3 ps-1.5 sm:flex">
          <div
            className="flex size-7 items-center justify-center rounded-lg bg-primary text-xs font-bold text-primary-foreground"
            aria-hidden="true"
          >
            {displayName.charAt(0).toUpperCase()}
          </div>
          <div className="leading-none">
            <div className="max-w-[110px] truncate text-xs font-bold text-foreground">
              {displayName}
            </div>
            {displayRole && (
              <div className="mt-0.5 max-w-[130px] truncate text-[10px] font-medium text-muted-foreground">
                {displayRole}
              </div>
            )}
          </div>
          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              title="تسجيل الخروج"
              aria-label="تسجيل الخروج"
              className="ms-1 rounded-lg p-1 text-muted-foreground transition-colors hover:bg-destructive-light hover:text-destructive-foreground"
            >
              <LogOut className="size-3.5" />
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
