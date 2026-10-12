import { useEffect, useRef } from "react"
import { Camera as CameraIcon, LayoutGrid, LogOut, MonitorPlay, ShieldAlert, Settings, Wifi, WifiOff, X } from "lucide-react"
import type { HealthResponse, MeResponse } from "@/types"
import type { TabKey } from "@/types/app"
import { ROLE_LABEL, SECTOR_LABEL, TAB_TITLES } from "@/lib/domain"
import { Button } from "@/components/ui/button"
import { LiveDot } from "@/shared/LiveDot"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import nexoraLogoWhite from "@/assets/logo/nexora-logo-full-white.svg"

interface Props {
  activeTab: TabKey
  onTabChange: (tab: TabKey) => void
  mobile: boolean
  open: boolean
  dark: boolean
  user: MeResponse | undefined
  health: HealthResponse | undefined
  healthLoading: boolean
  healthError: boolean
  onRetryHealth: () => void
  cameraCount: number
  runningCount: number
  onLogout: () => void
  onClose: () => void
}

const navigation: Array<{ id: TabKey; icon: typeof LayoutGrid }> = [
  { id: "overview", icon: LayoutGrid },
  { id: "live", icon: MonitorPlay },
  { id: "cameras", icon: CameraIcon },
  { id: "violations", icon: ShieldAlert },
]

export function Sidebar({ activeTab, onTabChange, mobile, open, dark, user, health, healthLoading, healthError, onRetryHealth, cameraCount, runningCount, onLogout, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const userName = user?.username ?? "مستخدم Nexora"
  const role = user ? `${ROLE_LABEL[user.role] ?? user.role} · ${SECTOR_LABEL[user.sector] ?? "حساب محلي"}` : "حساب محلي"
  const serverOk = health?.status === "ok" && !healthError

  useEffect(() => {
    if (mobile && open) closeRef.current?.focus()
  }, [mobile, open])

  return (
    <aside
      id="app-sidebar"
      aria-label="التنقل الرئيسي"
      aria-hidden={mobile && !open}
      inert={mobile && !open}
      className={`fixed inset-y-0 right-0 z-[60] flex h-dvh w-[min(86vw,300px)] shrink-0 flex-col border-s border-sidebar-border bg-sidebar transition-transform duration-300 lg:sticky lg:top-0 lg:z-20 lg:w-[264px] lg:translate-x-0 lg:shadow-none ${mobile && !open ? "translate-x-full" : "translate-x-0 shadow-floating"}`}
    >
      <div className="relative flex h-[68px] shrink-0 items-center justify-center border-b border-sidebar-border bg-gradient-to-b from-primary-light/80 to-transparent px-4">
        <img src={dark ? nexoraLogoWhite : nexoraLogoColor} alt="Nexora" className="h-9 max-w-[168px] object-contain" />
        {mobile && (
          <button ref={closeRef} type="button" aria-label="إغلاق القائمة" onClick={onClose} className="tap-target absolute start-3 top-3 flex items-center justify-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground">
            <X className="size-4" />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto p-4">
        <div className="space-y-1.5">
          <p className="mb-2 px-3 text-[11px] font-bold tracking-wide text-muted-foreground">القائمة الرئيسية</p>
          {navigation.map(({ id, icon: Icon }) => {
            const active = activeTab === id
            return (
              <button
                key={id}
                type="button"
                aria-current={active ? "page" : undefined}
                onClick={() => onTabChange(id)}
                className={`group relative flex min-h-12 w-full items-center gap-3 rounded-xl px-3 text-sm font-semibold transition-colors ${active ? "bg-primary-light text-primary ring-1 ring-inset ring-primary/20" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
              >
                {active && <span aria-hidden="true" className="absolute end-0 top-1/2 h-7 w-1 -translate-y-1/2 rounded-s-full bg-primary" />}
                <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg transition-colors ${active ? "bg-primary text-primary-foreground shadow-sm" : "bg-muted text-muted-foreground group-hover:text-foreground"}`}><Icon className="size-4" /></span>
                <span className="flex-1 truncate text-start">{TAB_TITLES[id]}</span>
                {id === "live" && runningCount > 0 && <span className="flex items-center gap-1.5 text-[10px] font-semibold text-success-foreground"><LiveDot className="size-1.5" active /> {runningCount}</span>}
              </button>
            )
          })}
        </div>
        <div className="space-y-1.5 border-t border-border/60 pt-5">
          <p className="mb-2 px-3 text-[11px] font-bold tracking-wide text-muted-foreground">النظام</p>
          <button type="button" disabled className="flex min-h-12 w-full items-center gap-3 rounded-xl px-3 text-sm font-semibold text-muted-foreground/65" title="الإعدادات ستتوفر لاحقًا">
            <span className="flex size-9 items-center justify-center rounded-lg bg-muted"><Settings className="size-4" /></span>
            <span className="flex-1 text-start">الإعدادات</span>
            <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px]">قريبًا</span>
          </button>
        </div>
      </nav>

      <div className="shrink-0 border-t border-sidebar-border bg-muted/40 p-4">
        <div className="mb-3 flex items-center justify-between gap-2 text-xs">
          <span className="font-semibold text-muted-foreground">حالة الخادم</span>
          {healthLoading ? <span className="text-muted-foreground">جارٍ الفحص...</span> : healthError ? <button type="button" onClick={onRetryHealth} className="font-bold text-destructive-foreground">غير متصل · أعد الفحص</button> : <span className={`flex items-center gap-2 font-bold ${serverOk ? "text-success-foreground" : "text-destructive-foreground"}`}><LiveDot tone={serverOk ? "success" : "destructive"} active={serverOk} />{serverOk ? "متصل" : "غير متصل"}</span>}
        </div>
        {health && (
          <div className="space-y-2 text-[11px] text-muted-foreground">
            <div className="flex justify-between"><span>واجهة النظام</span><span className={`font-semibold ${serverOk ? "text-foreground" : "text-destructive-foreground"}`}>{serverOk ? <><Wifi className="me-1 inline size-3" />يعمل</> : <><WifiOff className="me-1 inline size-3" />متوقف</>}</span></div>
            <div className="flex justify-between"><span>الكاميرات المسجلة</span><span className="font-semibold tabular-nums text-foreground">{cameraCount}</span></div>
            <div className="flex justify-between"><span>تعمل الآن</span><span className="font-bold tabular-nums text-primary">{runningCount}</span></div>
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-sidebar-border p-4">
        <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-2.5 ring-1 ring-border/70">
          <div className="relative shrink-0" aria-hidden="true">
            <div className="flex size-10 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">{userName.charAt(0).toLocaleUpperCase()}</div>
            <span className="absolute -bottom-0.5 -end-0.5 size-3 rounded-full bg-success ring-2 ring-card" />
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-sm font-semibold">{userName}</div>
            <div className="mt-1 truncate text-[11px] text-muted-foreground">{role}</div>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onLogout} aria-label="تسجيل الخروج" title="تسجيل الخروج" className="tap-target shrink-0 rounded-lg text-muted-foreground hover:bg-destructive-light hover:text-destructive"><LogOut className="size-4" /></Button>
        </div>
      </div>
    </aside>
  )
}
