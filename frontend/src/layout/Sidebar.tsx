import { useState, type ReactNode } from "react"
import {
  Camera as CameraIcon,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  Loader2,
  LogOut,
  MonitorPlay,
  Settings,
  ShieldAlert,
  Wifi,
  WifiOff,
  X,
} from "lucide-react"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import nexoraLogoWhite from "@/assets/logo/nexora-logo-full-white.svg"
import { Badge } from "@/components/ui/badge"
import { TAB_TITLES } from "@/lib/formatters"
import type { HealthResponse, TabKey } from "@/types"

interface NavItemProps {
  icon: ReactNode
  label: string
  active: boolean
  collapsed: boolean
  onClick: () => void
  badge?: number
  hint?: string
  disabled?: boolean
}

function NavItem({
  icon,
  label,
  active,
  collapsed,
  onClick,
  badge,
  hint,
  disabled,
}: NavItemProps) {
  return (
    <button
      type="button"
      title={collapsed ? label : undefined}
      aria-label={collapsed ? label : undefined}
      aria-current={active ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={`group relative flex min-h-11 w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-semibold transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 ${
        collapsed ? "justify-center" : ""
      } ${
        active
          ? "bg-primary-light text-primary ring-1 ring-inset ring-primary/25 shadow-xs"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      {active && (
        <span
          aria-hidden="true"
          className="absolute end-0 top-1/2 h-7 w-1 -translate-y-1/2 rounded-s-full bg-primary"
        />
      )}
      <span
        className={`relative flex size-9 shrink-0 items-center justify-center rounded-xl transition-colors ${
          active
            ? "bg-primary text-primary-foreground shadow-sm"
            : "bg-muted text-muted-foreground group-hover:text-foreground"
        }`}
      >
        {icon}
        {collapsed && badge !== undefined && badge > 0 && (
          <span className="absolute -start-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-white ring-2 ring-sidebar">
            {badge > 9 ? "9+" : badge}
          </span>
        )}
      </span>
      {!collapsed && (
        <>
          <span className="flex-1 truncate text-start">{label}</span>
          {hint && (
            <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-bold text-muted-foreground">
              {hint}
            </span>
          )}
          {badge !== undefined && badge > 0 && (
            <Badge
              variant="destructive"
              className="h-5 min-w-[20px] justify-center px-1.5 text-[11px] font-bold"
            >
              {badge > 99 ? "99+" : badge}
            </Badge>
          )}
        </>
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
  const [desktopCollapsed, setDesktopCollapsed] = useState(false)
  const collapsed = !isMobile && desktopCollapsed
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
        className={`fixed right-0 top-0 z-50 flex h-dvh shrink-0 flex-col border-l border-sidebar-border bg-sidebar transition-all duration-300 lg:sticky ${
          collapsed ? "w-[84px]" : "w-[280px]"
        } ${sidebarHidden ? "translate-x-full" : "translate-x-0 shadow-2xl lg:shadow-none"}`}
      >
        <div
          className={`relative flex h-16 shrink-0 items-center border-b border-sidebar-border bg-gradient-to-b from-primary-light via-primary-light/40 to-transparent px-4 ${
            collapsed ? "justify-center" : "justify-between"
          }`}
        >
          {!collapsed ? (
            <img
              src={dark ? nexoraLogoWhite : nexoraLogoColor}
              alt="Nexora"
              className="h-9 w-auto max-w-[168px] object-contain"
            />
          ) : (
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-base font-bold text-primary-foreground shadow-sm">
              N
            </div>
          )}

          {!isMobile && (
            <button
              type="button"
              aria-label={collapsed ? "توسيع القائمة الجانبية" : "طي القائمة الجانبية"}
              title={collapsed ? "توسيع القائمة" : "طي القائمة"}
              onClick={() => setDesktopCollapsed((c) => !c)}
              className={`flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground ${
                collapsed ? " absolute -left-3.5 top-5 z-20 border border-border bg-card shadow-md" : ""
              }`}
            >
              {collapsed ? <ChevronLeft className="size-4" /> : <ChevronRight className="size-4" />}
            </button>
          )}

          {isMobile && (
            <button
              type="button"
              aria-label="إغلاق القائمة"
              onClick={onCloseMobile}
              className="flex size-10 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="size-5" />
            </button>
          )}
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto p-3.5">
          <div className="space-y-1.5">
            {!collapsed && (
              <p className="mb-2 px-2.5 text-[11px] font-bold tracking-wide text-muted-foreground">
                مركز العمليات
              </p>
            )}
            {navItems.map((item) => (
              <NavItem
                key={item.id}
                icon={item.icon}
                label={TAB_TITLES[item.id]}
                active={tab === item.id}
                collapsed={collapsed}
                badge={item.badge}
                onClick={() => {
                  onSelectTab(item.id)
                  if (isMobile) onCloseMobile()
                }}
              />
            ))}
          </div>
          <div className="space-y-1.5 border-t border-border/50 pt-5">
            {!collapsed && (
              <p className="mb-2 px-2.5 text-[11px] font-bold tracking-wide text-muted-foreground">
                النظام
              </p>
            )}
            <NavItem
              icon={<Settings className="size-4" />}
              label="الإعدادات"
              active={false}
              collapsed={collapsed}
              hint="قريبًا"
              disabled
              onClick={() => {}}
            />
          </div>
        </nav>

        {!collapsed ? (
          <div className="shrink-0 border-t border-sidebar-border bg-muted/40 p-4">
            <div className="mb-3 flex items-center justify-between text-xs">
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
                  <span
                    className={`font-semibold ${
                      serverOk ? "text-foreground" : "text-destructive-foreground"
                    }`}
                  >
                    {serverOk ? "يعمل بكفاءة" : "متوقف"}
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
        ) : (
          <div className="flex shrink-0 flex-col items-center gap-2 border-t border-sidebar-border bg-muted/40 py-3">
            <span
              title={serverOk ? `الخادم متصل · ${runningCount}/${totalCams} كاميرا نشطة` : "الخادم غير متصل"}
              className={`flex size-9 items-center justify-center rounded-xl ${
                serverOk ? "bg-success-light text-success-foreground" : "bg-destructive-light text-destructive-foreground"
              }`}
            >
              {serverOk ? <Wifi className="size-4" /> : <WifiOff className="size-4" />}
            </span>
          </div>
        )}

        <div className="shrink-0 border-t border-sidebar-border p-3.5">
          {!collapsed ? (
            <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-2.5 ring-1 ring-border">
              <div className="relative shrink-0" aria-hidden="true">
                <div className="flex size-10 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                  {displayName.charAt(0).toUpperCase()}
                </div>
                <span className="absolute -bottom-0.5 -end-0.5 size-3 rounded-full bg-success ring-2 ring-card" />
              </div>
              <div className="min-w-0 flex-1 leading-tight">
                <div className="truncate text-sm font-bold text-foreground">{displayName}</div>
                <div className="mt-0.5 truncate text-[11px] font-medium text-muted-foreground">
                  {displayRole}
                </div>
              </div>
              <button
                type="button"
                aria-label="تسجيل الخروج"
                title="تسجيل الخروج"
                onClick={onLogout}
                className="flex min-h-9 shrink-0 items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-bold text-muted-foreground transition-colors hover:bg-destructive-light hover:text-destructive-foreground"
              >
                <LogOut className="size-3.5" />
                <span>خروج</span>
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <button
                type="button"
                aria-label="تسجيل الخروج"
                title={`خروج (${displayName})`}
                onClick={onLogout}
                className="flex size-10 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-destructive-light hover:text-destructive-foreground"
              >
                <LogOut className="size-4" />
              </button>
            </div>
          )}
        </div>
      </aside>

      {isMobile && sidebarOpen && (
        <button
          type="button"
          aria-label="إغلاق القائمة"
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs"
          onClick={onCloseMobile}
        />
      )}
    </>
  )
}
