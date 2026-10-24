import { Bell, LogOut, Menu, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ROLE_LABEL, TAB_TITLES, num } from "@/lib/formatters"
import type { MeResponse, TabKey } from "@/types"

export default function Topbar({
  tab,
  user,
  healthy,
  refreshing,
  openEvents,
  onMenu,
  onRefresh,
  onEvents,
  onLogout,
}: {
  tab: TabKey
  user: MeResponse
  healthy: boolean
  refreshing: boolean
  openEvents?: number
  onMenu: () => void
  onRefresh: () => void
  onEvents: () => void
  onLogout: () => void
}) {
  return (
    <header className="topbar">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          className="md:hidden"
          variant="outline"
          size="icon"
          onClick={onMenu}
          aria-label="فتح قائمة التنقل"
        >
          <Menu />
        </Button>
        <div>
          <div className="mb-1 hidden text-[10px] text-muted-foreground sm:block">
            المنصة الصناعية <span className="mx-2 text-muted-foreground">/</span>غرفة العمليات
          </div>
          <div className="text-sm font-medium text-foreground">{TAB_TITLES[tab]}</div>
        </div>
      </div>
      <div className="flex items-center gap-2 sm:gap-4">
        <span className={`badge hidden lg:inline-flex ${healthy ? "badge-success" : ""}`}>
          <span className="status-dot" />
          {healthy ? "الخادم متصل" : "بانتظار الخادم"}
        </span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="تحديث البيانات"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={refreshing ? "" : ""} />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="relative"
          aria-label={`عرض التنبيهات، ${openEvents} تنبيهات مفتوحة`}
          onClick={onEvents}
        >
          <Bell />
          {openEvents ? (
            <span className="latin absolute -end-1.5 -top-1.5 rounded bg-destructive px-1 text-[9px] font-bold text-background">
              {num(openEvents > 99 ? 99 : openEvents)}
            </span>
          ) : null}
        </Button>
        <div className="hidden border-s border-border ps-4 text-start sm:block">
          <p className="latin text-xs text-foreground">{user.username}</p>
          <p className="mt-1 text-[10px] text-muted-foreground">{ROLE_LABEL[user.role]}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onLogout} aria-label="تسجيل الخروج">
          <LogOut />
        </Button>
      </div>
    </header>
  )
}
