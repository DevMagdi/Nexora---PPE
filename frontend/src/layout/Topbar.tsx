import { Bell, Clock, Menu, Moon, Sun } from "lucide-react"
import { Button } from "@/components/ui/button"
import { formatClock, formatRelative, TAB_TITLES, violationLabel } from "@/lib/formatters"
import ErrorState from "@/shared/ErrorState"
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
            className="-me-1 rounded-xl p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Menu className="size-5" />
          </button>
        )}
        <div className="min-w-0">
          <nav aria-label="مسار التنقل" className="flex items-center gap-1.5 truncate text-[11px] text-muted-foreground">
            <span>Nexora</span>
            {crumbs.map((c) => (
              <span key={c} className="flex items-center gap-1.5">
                <span aria-hidden="true">/</span>
                {c}
              </span>
            ))}
          </nav>
          <h1 className="truncate text-lg font-bold lg:text-xl">{TAB_TITLES[tab]}</h1>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        <SegToggle
          checked={range === "7d"}
          onChange={(v) => onRangeChange(v ? "7d" : "24h")}
          labelOn="7 أيام"
          labelOff="اليوم"
        />

        <div className="hidden h-6 w-px bg-border/60 md:block" />

        <div className="hidden items-center gap-2 text-sm tabular-nums text-muted-foreground sm:flex">
          <Clock className="size-3.5 opacity-70" />
          <time dateTime={new Date(now).toISOString()}>{formatClock(now)}</time>
        </div>

        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label={dark ? "التبديل إلى الوضع الفاتح" : "التبديل إلى الوضع الداكن"}
          onClick={onToggleDark}
          className="rounded-xl hover:bg-muted"
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
            className="relative rounded-xl hover:bg-muted"
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
              <div className="card-premium absolute left-0 top-12 z-50 w-80 max-w-[90vw] animate-fade-in overflow-hidden rounded-2xl border border-border/60 p-2">
                <p className="px-3 py-2 text-xs font-bold text-muted-foreground">آخر التنبيهات</p>

                {overviewError && !hasOverviewRaw ? (
                  <div className="px-3 pb-3">
                    <ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={onRetryOverview} />
                  </div>
                ) : overviewList.length === 0 ? (
                  <p className="px-3 pb-3 text-sm text-muted-foreground">لا توجد تنبيهات في {rangeLabel}.</p>
                ) : (
                  overviewList.slice(0, 5).map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      onClick={() => {
                        onCloseBell()
                        onOpenFrame(v.frame_url)
                      }}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-start transition-colors hover:bg-muted/40"
                    >
                      <span className="size-2 shrink-0 rounded-full bg-destructive" />
                      <span className="flex-1 truncate text-sm font-semibold">
                        {violationLabel(v.violation_type, ppeLabels)}
                      </span>
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {formatRelative(v.timestamp, now)}
                      </span>
                    </button>
                  ))
                )}

                <button
                  type="button"
                  onClick={() => {
                    onCloseBell()
                    onGoViolations()
                  }}
                  className="mt-1 w-full rounded-xl px-3 py-2 text-center text-xs font-bold text-primary hover:bg-primary/10"
                >
                  عرض السجل الكامل
                </button>
              </div>
            </>
          )}
        </div>

        <div
          className="flex size-9 items-center justify-center rounded-full bg-primary-light text-xs font-bold text-primary"
          aria-hidden="true"
        >
          {displayName.charAt(0)}
        </div>
      </div>
    </header>
  )
}
