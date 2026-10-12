import type { ReactNode } from "react"
import { Camera as CameraIcon, LayoutGrid, Loader2, MonitorPlay, Settings, ShieldAlert, Wifi, WifiOff, X } from "lucide-react"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import nexoraLogoWhite from "@/assets/logo/nexora-logo-full-white.svg"
import { Badge } from "@/components/ui/badge"
import { TAB_TITLES } from "@/lib/formatters"
import type { HealthResponse, TabKey } from "@/types"

interface NavItemProps {
  icon: ReactNode
  label: string
  active: boolean
  onClick: () => void
  badge?: number
  hint?: string
  disabled?: boolean
}

function NavItem({ icon, label, active, onClick, badge, hint, disabled }: NavItemProps) {
  return (
    <button
      type="button"
      aria-current={active ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={`group relative flex min-h-11 w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        active
          ? "bg-primary-light text-primary ring-1 ring-inset ring-primary/25"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      {active && (
        <span aria-hidden="true" className="absolute end-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-s-full bg-primary" />
      )}
      <span
        className={`flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors ${
          active
            ? "bg-primary text-primary-foreground shadow-sm"
            : "bg-muted text-muted-foreground group-hover:text-foreground"
        }`}
      >
        {icon}
      </span>
      <span className="flex-1 truncate text-start">{label}</span>
      {hint && <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-bold text-muted-foreground">{hint}</span>}
      {badge !== undefined && badge > 0 && (
        <Badge variant="destructive" className="h-5 min-w-[18px] justify-center px-1.5 text-[11px] font-bold">
          {badge > 99 ? "99+" : badge}
        </Badge>
      )}
    </button>
  )
}

export interface SidebarProps {
  tab: TabKey
  onSelectTab: (tab: TabKey) => void
  unseenCount: number
  isMobile: boolean
  sidebarOpen: boolean
  onCloseMobile: () => void
  dark: boolean
  health: HealthResponse | undefined
  healthLoading: boolean
  healthError: boolean
  onRetryHealth: () => void
  totalCams: number
  runningCount: number
  displayName: string
  displayRole: string
  onLogout: () => void
}

export default function Sidebar({
  tab,
  onSelectTab,
  unseenCount,
  isMobile,
  sidebarOpen,
  onCloseMobile,
  dark,
  health,
  healthLoading,
  healthError,
  onRetryHealth,
  totalCams,
  runningCount,
  displayName,
  displayRole,
  onLogout,
}: SidebarProps) {
  const sidebarHidden = isMobile && !sidebarOpen
  const serverOk = health?.status === "ok" && !healthError

  const navItems: { id: TabKey; icon: ReactNode; badge?: number }[] = [
    { id: "overview", icon: <LayoutGrid className="size-4" /> },
    { id: "live", icon: <MonitorPlay className="size-4" /> },
    { id: "cameras", icon: <CameraIcon className="size-4" /> },
    { id: "violations", icon: <ShieldAlert className="size-4" />, badge: unseenCount },
  ]

  return (
    <>
      <aside
        id="app-sidebar"
        aria-label="التنقل الرئيسي"
        {...(sidebarHidden ? ({ inert: true } as Record<string, unknown>) : {})}
        className={`fixed right-0 top-0 z-50 flex h-dvh w-[280px] shrink-0 flex-col border-l border-sidebar-border bg-sidebar transition-transform duration-300 lg:sticky ${
          sidebarHidden ? "translate-x-full" : "translate-x-0 shadow-2xl lg:shadow-none"
        }`}
      >
        <div className="relative flex h-16 shrink-0 items-center justify-center border-b border-sidebar-border bg-gradient-to-b from-primary-light via-primary-light/40 to-transparent">
          <img
            src={dark ? nexoraLogoWhite : nexoraLogoColor}
            alt="Nexora"
            className="h-9 w-auto max-w-[168px] object-contain"
          />
          {isMobile && (
            <button
              type="button"
              aria-label="إغلاق القائمة"
              onClick={onCloseMobile}
              className="absolute left-3 top-3 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          )}
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto p-4">
          <div className="space-y-1.5">
            <p className="mb-2 px-2.5 text-xs font-semibold text-muted-foreground">القائمة الرئيسية</p>
            {navItems.map((item) => (
              <NavItem
                key={item.id}
                icon={item.icon}
                label={TAB_TITLES[item.id]}
                active={tab === item.id}
                badge={item.badge}
                onClick={() => {
                  onSelectTab(item.id)
                  if (isMobile) onCloseMobile()
                }}
              />
            ))}
          </div>
          <div className="space-y-1.5 border-t border-border/40 pt-5">
            <p className="mb-2 px-2.5 text-xs font-semibold text-muted-foreground">النظام</p>
            <NavItem
              icon={<Settings className="size-4" />}
              label="الإعدادات"
              active={false}
              hint="قريبًا"
              disabled
              onClick={() => {}}
            />
          </div>
        </nav>

        <div className="shrink-0 border-t border-sidebar-border bg-muted/50 p-4">
          <div className="mb-3.5 flex items-center justify-between text-xs">
            <span className="font-semibold text-muted-foreground">حالة الخادم</span>
            {healthLoading ? (
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> جارٍ الفحص...
              </span>
            ) : healthError ? (
              <button
                type="button"
                onClick={onRetryHealth}
                className="flex items-center gap-1.5 font-bold text-destructive-foreground"
              >
                <WifiOff className="size-3.5" /> غير متصل
              </button>
            ) : (
              <span
                className={`flex items-center gap-1.5 font-bold ${
                  serverOk ? "text-success-foreground" : "text-destructive-foreground"
                }`}
              >
                {serverOk ? <Wifi className="size-3.5" /> : <WifiOff className="size-3.5" />}
                {serverOk ? "متصل" : "غير متصل"}
              </span>
            )}
          </div>

          {health && (
            <div className="space-y-2 text-[11px] text-muted-foreground">
              <div className="flex justify-between">
                <span>واجهة النظام</span>
                <span className={`font-semibold ${serverOk ? "text-foreground" : "text-destructive-foreground"}`}>
                  {serverOk ? "يعمل" : "متوقف"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>الكاميرات المُسجّلة</span>
                <span className="font-semibold tabular-nums text-foreground">{totalCams}</span>
              </div>
              <div className="flex justify-between">
                <span>تعمل الآن</span>
                <span className="font-bold tabular-nums text-primary">{runningCount}</span>
              </div>
            </div>
          )}
        </div>

        <div className="shrink-0 border-t border-sidebar-border p-4">
          <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-2.5 ring-1 ring-border">
            <div className="relative shrink-0" aria-hidden="true">
              <div className="flex size-10 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                {displayName.charAt(0)}
              </div>
              <span className="absolute -bottom-0.5 -end-0.5 size-3 rounded-full bg-success ring-2 ring-card" />
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-sm font-semibold">{displayName}</div>
              <div className="mt-0.5 truncate text-xs text-muted-foreground">{displayRole}</div>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="shrink-0 rounded-lg px-2 py-1 text-[11px] font-bold text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              خروج
            </button>
          </div>
        </div>
      </aside>

      {isMobile && sidebarOpen && (
        <button
          type="button"
          aria-label="إغلاق القائمة"
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm"
          onClick={onCloseMobile}
        />
      )}
    </>
  )
}
