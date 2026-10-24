import { useEffect, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, X } from "lucide-react"
import Sidebar from "@/layout/Sidebar"
import Topbar from "@/layout/Topbar"
import Overview from "@/dashboard/Overview"
import LivePage from "@/dashboard/LivePage"
import UploadsPage from "@/dashboard/UploadsPage"
import SitesPage from "@/dashboard/SitesPage"
import UsersPage from "@/dashboard/UsersPage"
import CamerasPage from "@/cameras/CamerasPage"
import ViolationsPage from "@/violations/ViolationsPage"
import Modal from "@/components/Modal"
import { Empty, ErrorPanel, Loading } from "@/components/Feedback"
import { Button } from "@/components/ui/button"
import {
  useCameras,
  useDashboard,
  useHealth,
  useRefresh,
  useSites,
  useSystem,
} from "@/hooks/useNexora"
import { logout, resolveFrameUrl, resolveViolation } from "@/lib/api"
import { TAB_TITLES, formatDate, formatTime } from "@/lib/formatters"
import { getErrorMessage } from "@/lib/utils"
import type { MeResponse, RangeKey, TabKey, Violation } from "@/types"

const DESCRIPTIONS: Record<TabKey, string> = {
  overview: "رؤية تشغيلية موحّدة للسلامة في مصانعك ومواقعك الصناعية.",
  live: "راقب معدات الوقاية والمخالفات من مصادر موقعك، في الوقت الفعلي.",
  cameras: "إعداد مصادر المراقبة وربطها بالمصانع والمواقع وقواعد السلامة.",
  uploads: "استدلال صناعي على صور ومقاطع من موقع العمل، باستخدام الكاشف نفسه.",
  violations: "راجع الأدلة المرئية، تابع الأحداث المفتوحة، ووثّق المعالجة.",
  sites: "نظّم مصادر المراقبة حسب المصانع ومواقع الإنشاء والورش والمستودعات.",
  users: "وصول واضح للمدير والمشرف والمشاهد، مع إدارة محلية للحسابات.",
}
function validTab(value: string, user: MeResponse): TabKey {
  if (
    !(value in TAB_TITLES) ||
    (value === "users" && user.role !== "admin") ||
    (value === "uploads" && user.role === "viewer")
  )
    return "overview"
  return value as TabKey
}

export default function App({ user }: { user: MeResponse }) {
  const [tab, setTab] = useState<TabKey>(() => validTab(window.location.hash.slice(1), user))
  const [mobile, setMobile] = useState(false)
  const [range, setRange] = useState<RangeKey>("24h")
  const [site, setSite] = useState("")
  const [selected, setSelected] = useState<number | null>(null)
  const [evidence, setEvidence] = useState<Violation | null>(null)
  const [toast, setToast] = useState<{ message: string; error: boolean } | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const cameras = useCameras()
  const sites = useSites()
  const system = useSystem()
  const health = useHealth()
  const stats = useDashboard(range, site ? Number(site) : undefined)
  const refresh = useRefresh()
  const client = useQueryClient()
  const canOperate = user.role !== "viewer"
  const notify = (message: string, error = false) => setToast({ message, error })
  const resolve = useMutation({
    mutationFn: resolveViolation,
    onSuccess: async () => {
      await refresh()
      notify("تم توثيق معالجة الحدث")
    },
    onError: (error) => notify(getErrorMessage(error), true),
  })
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      client.clear()
      window.location.assign("/")
    },
    onError: (error) => notify(getErrorMessage(error), true),
  })

  useEffect(() => {
    const change = () => setTab(validTab(window.location.hash.slice(1), user))
    window.addEventListener("hashchange", change)
    return () => window.removeEventListener("hashchange", change)
  }, [user])
  useEffect(() => {
    if (!toast) return
    const timeout = setTimeout(() => setToast(null), toast.error ? 8000 : 4500)
    return () => clearTimeout(timeout)
  }, [toast])
  function navigate(next: TabKey) {
    const valid = validTab(next, user)
    setTab(valid)
    window.history.pushState(null, "", `#${valid}`)
    setMobile(false)
  }
  function live(id: number) {
    setSelected(id)
    navigate("live")
  }
  async function refreshAll() {
    setRefreshing(true)
    try {
      await Promise.all([refresh(), health.refetch(), stats.refetch()])
    } finally {
      setRefreshing(false)
    }
  }
  const cameraList = cameras.data ?? []
  const siteList = sites.data ?? []
  const pendingId = resolve.isPending ? resolve.variables : undefined
  const commonEvents = {
    cameras: cameraList,
    canOperate,
    pendingId,
    onResolve: (id: number) => resolve.mutate(id),
    onEvidence: setEvidence,
  }
  const frameUrl = resolveFrameUrl(evidence?.frame_url ?? null)
  let content
  if (cameras.isPending || sites.isPending) content = <Loading />
  else if (cameras.isError || sites.isError)
    content = (
      <div className="panel">
        <ErrorPanel error={cameras.error || sites.error} retry={() => void refreshAll()} />
      </div>
    )
  else if (tab === "overview")
    content = (
      <Overview
        {...commonEvents}
        data={stats.data}
        loading={stats.isPending}
        error={stats.error}
        retry={() => void stats.refetch()}
        range={range}
        siteId={site ? Number(site) : undefined}
        onNavigate={navigate}
      />
    )
  else if (tab === "live")
    content = (
      <LivePage
        cameras={cameraList}
        sites={siteList}
        selectedId={selected}
        onSelect={setSelected}
        canOperate={canOperate}
        refresh={refresh}
      />
    )
  else if (tab === "cameras")
    content = (
      <CamerasPage
        cameras={cameraList}
        sites={siteList}
        meta={system.data}
        canOperate={canOperate}
        onLive={live}
        refresh={refresh}
        notify={notify}
      />
    )
  else if (tab === "uploads")
    content = <UploadsPage sites={siteList} meta={system.data} refresh={refresh} onLive={live} />
  else if (tab === "sites")
    content = (
      <SitesPage
        sites={siteList}
        cameras={cameraList}
        isAdmin={user.role === "admin"}
        refresh={refresh}
      />
    )
  else if (tab === "users") content = <UsersPage refresh={refresh} />
  else
    content = stats.isPending ? (
      <Loading />
    ) : stats.isError ? (
      <ErrorPanel error={stats.error} retry={() => void stats.refetch()} />
    ) : (
      <ViolationsPage
        key={`${range}-${site}`}
        {...commonEvents}
        from={stats.data?.from}
        to={stats.data?.to}
        siteId={site ? Number(site) : undefined}
      />
    )

  return (
    <div className="app-shell" dir="rtl" lang="ar">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-primary focus:p-3 focus:text-background"
      >
        تجاوز إلى المحتوى
      </a>
      <Sidebar
        tab={tab}
        onNavigate={navigate}
        role={user.role}
        model={system.data}
        open={mobile}
        onClose={() => setMobile(false)}
      />
      <div className="app-main">
        <Topbar
          tab={tab}
          user={user}
          healthy={health.data?.status === "ok" && !health.isError}
          refreshing={refreshing}
          openEvents={stats.data?.open_events}
          onMenu={() => setMobile(true)}
          onRefresh={() => void refreshAll()}
          onEvents={() => navigate("violations")}
          onLogout={() => {
            if (!signOut.isPending) signOut.mutate()
          }}
        />
        <main id="main-content" tabIndex={-1} className="workspace">
          <div className="page-head">
            <div>
              <div className="eyebrow" dir="ltr">
                MANTIK / INDUSTRIAL OPERATIONS
              </div>
              <h1>{TAB_TITLES[tab]}</h1>
              <p>{DESCRIPTIONS[tab]}</p>
            </div>
            {(tab === "overview" || tab === "violations") && (
              <div className="flex flex-wrap items-center gap-3">
                <select
                  className="field !h-10 !w-auto max-w-[220px]"
                  aria-label="تصفية حسب الموقع"
                  value={site}
                  onChange={(event) => setSite(event.target.value)}
                >
                  <option value="">جميع المواقع</option>
                  {siteList.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
                <div className="segmented">
                  <button aria-pressed={range === "24h"} onClick={() => setRange("24h")}>
                    24 ساعة
                  </button>
                  <button aria-pressed={range === "7d"} onClick={() => setRange("7d")}>
                    7 أيام
                  </button>
                </div>
              </div>
            )}
          </div>
          <div className="page-enter" key={tab}>
            {content}
          </div>
          <footer className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6 text-[9px] text-muted-foreground">
            <span>مصانع · مواقع إنشاء · ورش صناعية · مستودعات</span>
            <span className="latin tracking-wider" dir="ltr">
              MANTIK PPE · LOCAL INDUSTRIAL INTELLIGENCE
            </span>
          </footer>
        </main>
      </div>
      <Modal
        open={evidence !== null}
        onClose={() => setEvidence(null)}
        title={`دليل الحدث ${evidence?.id ?? ""}`}
        description={
          evidence
            ? `${formatDate(evidence.timestamp)} · ${formatTime(evidence.timestamp)}`
            : "لقطة من موقع العمل"
        }
        wide
      >
        {frameUrl ? (
          <img
            className="max-h-[65vh] w-full rounded-lg bg-muted object-contain"
            src={frameUrl}
            alt="الدليل المرئي للمخالفة الصناعية"
          />
        ) : (
          <Empty
            title="الدليل غير متاح"
            description="قد تكون اللقطة حُذفت وفق سياسة الاحتفاظ بالأدلة."
          />
        )}
      </Modal>
      {toast && (
        <div
          className={`toast ${toast.error ? "!border-destructive/40" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          {!toast.error && <CheckCircle2 className="size-5 shrink-0 text-success" />}
          <p className={toast.error ? "text-destructive" : "text-foreground"}>{toast.message}</p>
          <Button
            variant="ghost"
            size="icon"
            aria-label="إغلاق الإشعار"
            onClick={() => setToast(null)}
          >
            <X />
          </Button>
        </div>
      )}
    </div>
  )
}
