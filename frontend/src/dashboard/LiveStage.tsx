import { useState, type ReactNode } from "react"
import {
  Activity,
  AlertTriangle,
  Boxes,
  Camera as CameraIcon,
  Eye,
  HardHat,
  Loader2,
  MonitorPlay,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Shirt,
  Square,
  Users,
  WifiOff,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useCountUp } from "@/hooks/useUiHooks"
import { getMjpegStreamUrl } from "@/lib/api"
import {
  cameraProfile,
  LIVE_STATUS_LABEL,
  PROFILE_LABEL,
  SOURCE_TYPE_SHORT,
  withParams,
} from "@/lib/formatters"
import Card from "@/shared/Card"
import EmptyState from "@/shared/EmptyState"
import ErrorState from "@/shared/ErrorState"
import LiveDot from "@/shared/LiveDot"
import SkeletonBlock from "@/shared/SkeletonBlock"
import type { Camera, LiveCounts, LiveMetricItem, LiveStatus } from "@/types"

function DockMetric({ value, label }: { value: number | undefined; label: string }) {
  const animated = useCountUp(value)
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] px-3.5 py-2 text-center backdrop-blur-md">
      <div className="text-base font-bold tabular-nums text-white">{animated ?? "—"}</div>
      <div className="mt-0.5 text-[11px] font-medium text-slate-300">{label}</div>
    </div>
  )
}

function SideMetric({
  icon,
  value,
  label,
}: {
  icon: ReactNode
  value: number | undefined
  label: string
}) {
  const animated = useCountUp(value)
  return (
    <div className="card-premium flex flex-col items-center justify-center gap-1 rounded-xl border border-border/60 p-3.5">
      {icon}
      <span className="text-lg font-bold tabular-nums">{animated ?? "—"}</span>
      <span className="text-[11px] font-bold text-muted-foreground">{label}</span>
    </div>
  )
}

function sideMetricIcon(label: string) {
  if (label === "أشخاص") return <Users className="size-4 text-info" />
  if (label === "خوذات") return <HardHat className="size-4 text-warning" />
  if (label === "سترات") return <Shirt className="size-4 text-highlight" />
  if (label === "إجمالي الكشف") return <Boxes className="size-4 text-primary" />
  if (label.includes("نظارات")) return <Eye className="size-4 text-warning" />
  if (label.includes("كمامة")) return <ShieldAlert className="size-4 text-destructive" />
  if (label.includes("قفاز")) return <ShieldAlert className="size-4 text-destructive" />
  if (label.includes("غطاء")) return <HardHat className="size-4 text-warning" />
  return <Boxes className="size-4 text-primary" />
}

export interface LiveStageProps {
  camera: Camera | null
  metrics: LiveMetricItem[]
  status: LiveStatus
  compliance: number | undefined
  skinHits?: number
  pending: boolean
  canOperate: boolean
  onStart: () => void
  onStop: () => void
  onGoCameras: () => void
  onStreamReady: () => void
  onStreamLost: () => void
}

export function LiveStage({
  camera,
  metrics,
  status,
  compliance,
  skinHits,
  pending,
  canOperate,
  onStart,
  onStop,
  onGoCameras,
  onStreamReady,
  onStreamLost,
}: LiveStageProps) {
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const currentStreamKey = `${camera?.id ?? "none"}-${camera?.is_running ?? false}-${nonce}`
  const streamError = errorKey === currentStreamKey

  const retry = () => {
    setErrorKey(null)
    setNonce((n) => n + 1)
  }

  if (!camera) {
    return (
      <div className="flex h-full min-h-[360px] w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-8 text-center">
        <div className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-primary-light text-primary">
          <MonitorPlay className="size-8" />
        </div>
        <h3 className="mb-2 text-xl font-bold text-foreground">اختر كاميرا لبدء المراقبة</h3>
        <p className="mb-6 max-w-sm text-sm leading-relaxed text-muted-foreground">
          اختر أحد المصادر من القائمة الجانبية لعرض البث المباشر والتحليل الذكي لمعدات الوقاية.
        </p>
        <Button type="button" variant="outline" onClick={onGoCameras} className="min-h-11 gap-2 rounded-xl px-5">
          <CameraIcon className="size-4" /> إدارة الكاميرات
        </Button>
      </div>
    )
  }

  if (!camera.is_running) {
    return (
      <div className="flex h-full min-h-[360px] w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-8 text-center">
        <div className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <WifiOff className="size-8" />
        </div>
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-xs font-bold text-muted-foreground">
          <span>الكاميرا #{camera.id}</span>
          <span>·</span>
          <span>{PROFILE_LABEL[cameraProfile(camera)]}</span>
        </div>
        <h3 className="mb-2 text-xl font-bold text-foreground">البث متوقف حاليًا</h3>
        <p className="mb-6 max-w-sm text-sm leading-relaxed text-muted-foreground">
          {canOperate
            ? `«${camera.name}» في وضع الاستعداد. شغّل البث لبدء التحليل اللحظي ورصد المخالفات.`
            : `«${camera.name}» متوقفة حاليًا. اطلب من مشغّل النظام تشغيل البث.`}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          {canOperate && (
            <button type="button" className="btn-cta" onClick={onStart} disabled={pending}>
              {pending ? (
                <>
                  <Loader2 className="size-4 animate-spin" /> جارٍ التشغيل...
                </>
              ) : (
                <>
                  <Play className="size-4 fill-current" /> تشغيل البث الآن
                </>
              )}
            </button>
          )}
          <Button type="button" variant="outline" onClick={onGoCameras} className="min-h-11 rounded-xl">
            إعدادات الكاميرا
          </Button>
        </div>
      </div>
    )
  }

  const streamSrc = withParams(getMjpegStreamUrl(camera.id), nonce ? { r: String(nonce) } : {})
  const isMedical = cameraProfile(camera) === "medical"

  return (
    <div className="flex h-full w-full flex-col bg-slate-950">
      {/* ─── Top Bar (around stream, non-intrusive) ─── */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-slate-900/95 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={`size-2.5 shrink-0 rounded-full ${
              status === "open"
                ? "bg-red-500 animate-pulse shadow-[0_0_12px_rgba(239,68,68,0.8)]"
                : "bg-amber-400"
            }`}
          />
          <div className="min-w-0">
            <h2 className="truncate text-sm font-bold text-white sm:text-base">{camera.name}</h2>
            <p className="truncate text-[11px] text-slate-400">
              المعرّف #{camera.id} · القطاع: {PROFILE_LABEL[cameraProfile(camera)]} ·{" "}
              {SOURCE_TYPE_SHORT[camera.source_type] ?? camera.source_type}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {skinHits !== undefined && skinHits > 0 && (
            <span className="hidden items-center gap-1 rounded-lg bg-emerald-500/20 px-2.5 py-1 text-[11px] font-bold text-emerald-300 ring-1 ring-emerald-400/30 sm:inline-flex">
              <Activity className="size-3" />
              <span>فلتر الجلد: {skinHits}</span>
            </span>
          )}
          <Badge
            className={`shrink-0 border-none px-3 py-1 text-xs font-bold text-white ${
              status === "open" ? "bg-red-600 live-ring" : "bg-amber-600"
            }`}
          >
            {status === "open" ? "LIVE · مباشر" : LIVE_STATUS_LABEL[status] || "جارٍ التحضير..."}
          </Badge>
        </div>
      </div>

      {/* ─── Clean Video Stage Frame ─── */}
      <div className="relative flex min-h-[260px] flex-1 items-center justify-center overflow-hidden bg-black">
        {streamError ? (
          <div className="flex max-w-md flex-col items-center justify-center p-8 text-center">
            <div className="mb-4 flex size-14 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-400 ring-1 ring-amber-400/30">
              <AlertTriangle className="size-7" />
            </div>
            <h3 className="mb-2 text-lg font-bold text-white">تعذّر استلام تدفق الفيديو</h3>
            <p className="mb-6 text-xs leading-relaxed text-slate-300">
              الكاميرا في حالة تشغيل لكن إطار البث لم يصل بعد. تحقق من اتصال مصدر الكاميرا أو أعد
              الاتصال بالبث.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={retry}
                className="min-h-10 gap-2 rounded-xl border-white/20 bg-white/10 text-white hover:bg-white/20"
              >
                <RefreshCw className="size-4" /> إعادة الاتصال بالبث
              </Button>
              {canOperate && (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={onStop}
                  disabled={pending}
                  className="min-h-10 gap-2 rounded-xl"
                >
                  <Square size={14} fill="currentColor" /> إيقاف المصدر
                </Button>
              )}
            </div>
          </div>
        ) : (
          <img
            key={camera.id}
            src={streamSrc}
            onLoad={onStreamReady}
            onError={() => {
              setErrorKey(currentStreamKey)
              onStreamLost()
            }}
            className="h-full w-full object-contain"
            alt={`البث المباشر من ${camera.name}`}
          />
        )}
      </div>

      {/* ─── Bottom Telemetry & Controls Dock (Not Cluttering Video) ─── */}
      <div className="shrink-0 border-t border-white/10 bg-slate-900/95 px-4 py-3.5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="grid flex-1 grid-cols-2 gap-2 text-xs sm:flex sm:flex-wrap sm:items-center sm:gap-2.5">
            {metrics.map((m) => (
              <DockMetric key={m.label} value={m.value} label={m.label} />
            ))}
            {!isMedical && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] px-3.5 py-2 text-center">
                <div
                  className={`text-base font-bold tabular-nums ${
                    compliance === undefined
                      ? "text-white"
                      : compliance >= 90
                        ? "text-emerald-400"
                        : compliance >= 70
                          ? "text-amber-400"
                          : "text-red-400"
                  }`}
                >
                  {compliance === undefined ? "—" : `${compliance}%`}
                </div>
                <div className="mt-0.5 text-[11px] font-medium text-slate-300">الالتزام</div>
              </div>
            )}
          </div>

          {canOperate && (
            <Button
              type="button"
              size="sm"
              variant="destructive"
              onClick={onStop}
              disabled={pending}
              className="min-h-10 w-full gap-2 rounded-xl px-4 shadow-lg shadow-destructive/25 sm:w-auto"
            >
              {pending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Square size={14} fill="currentColor" />
              )}
              <span>إيقاف البث</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export interface LiveViewSectionProps {
  cameraSearch: string
  onCameraSearchChange: (next: string) => void
  camerasError: boolean
  camerasLoading: boolean
  cameraList: Camera[]
  filteredCams: Camera[]
  selectedCamera: Camera | null
  ppeLabels: Map<string, string>
  isMedicalView: boolean
  compliance: number | undefined
  activeLiveStatus: LiveStatus
  overlayMetrics: LiveMetricItem[]
  activeCounts: LiveCounts
  camPending: boolean
  canOperate: boolean
  onRetryCameras: () => void
  onSelectCam: (id: number) => void
  onToggleCamera: (cam: Camera) => void
  onGoCameras: () => void
  onAddFirstCamera: () => void
  onStreamReady: () => void
  onStreamLost: () => void
}

export default function LiveViewSection({
  cameraSearch,
  onCameraSearchChange,
  camerasError,
  camerasLoading,
  cameraList,
  filteredCams,
  selectedCamera,
  ppeLabels,
  isMedicalView,
  compliance,
  activeLiveStatus,
  overlayMetrics,
  activeCounts,
  camPending,
  canOperate,
  onRetryCameras,
  onSelectCam,
  onToggleCamera,
  onGoCameras,
  onAddFirstCamera,
  onStreamReady,
  onStreamLost,
}: LiveViewSectionProps) {
  return (
    <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 lg:h-[calc(100dvh-7.5rem)] lg:grid-cols-12">
      <div className="flex flex-col gap-4 lg:col-span-3 lg:h-full lg:min-h-0">
        <Card className="flex max-h-[42vh] flex-1 flex-col overflow-hidden p-4 lg:max-h-none">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-bold text-muted-foreground">قائمة الكاميرات ({cameraList.length})</h3>
            <span className="text-[11px] font-semibold text-primary">
              {cameraList.filter((c) => c.is_running).length} نشطة
            </span>
          </div>

          <div className="relative mb-3.5">
            <Search className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="بحث بالاسم أو الكود..."
              aria-label="بحث عن كاميرا"
              className="h-10 rounded-xl border-border/60 bg-muted/40 pe-9 text-sm focus:bg-card"
              value={cameraSearch}
              onChange={(e) => onCameraSearchChange(e.target.value)}
            />
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto pe-1">
            {camerasError && cameraList.length === 0 ? (
              <ErrorState compact title="تعذّر تحميل الكاميرات" onRetry={onRetryCameras} />
            ) : camerasLoading && cameraList.length === 0 ? (
              <div className="space-y-2.5 py-2">
                {Array.from({ length: 3 }, (_, i) => (
                  <SkeletonBlock key={i} className="h-20 w-full rounded-xl" />
                ))}
              </div>
            ) : cameraList.length === 0 ? (
              <EmptyState
                compact
                icon={<CameraIcon className="size-6 text-primary" />}
                title="لا توجد كاميرات بعد"
                desc="اربط أول كاميرا وابدأ المراقبة الذكية خلال دقيقة."
                action={
                  canOperate ? (
                    <button type="button" className="btn-cta text-sm" onClick={onAddFirstCamera}>
                      <Plus className="size-4" /> أضف أول كاميرا
                    </button>
                  ) : undefined
                }
              />
            ) : filteredCams.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted-foreground">
                لا توجد نتائج مطابقة للبحث
              </div>
            ) : (
              filteredCams.map((c) => {
                const isSelected = selectedCamera?.id === c.id
                const classes = c.enabled_classes ?? []
                return (
                  <button
                    key={c.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => onSelectCam(c.id)}
                    className={`group flex w-full items-start gap-3 rounded-xl border p-3.5 text-start transition-all cursor-pointer ${
                      isSelected
                        ? "border-primary/40 bg-primary-light shadow-xs"
                        : "border-transparent hover:border-border/60 hover:bg-muted/50"
                    }`}
                  >
                    <span className="mt-1.5">
                      <LiveDot tone="success" active={c.is_running} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-bold text-foreground transition-colors group-hover:text-primary">
                          {c.name}
                        </span>
                        <span
                          className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                            c.is_running
                              ? "bg-success-light text-success-foreground"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {c.is_running ? "تعمل" : "متوقفة"}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="rounded border border-border/50 bg-card px-1.5 py-0.5 tabular-nums">
                          #{c.id}
                        </span>
                        <span className="truncate">
                          {PROFILE_LABEL[cameraProfile(c)]} · {SOURCE_TYPE_SHORT[c.source_type] ?? c.source_type}
                        </span>
                      </div>
                      {classes.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {classes.slice(0, 3).map((k) => (
                            <span
                              key={k}
                              className="rounded-md border border-border/30 bg-card/80 px-1.5 py-0.5 text-[10px] font-medium text-foreground/80"
                            >
                              {ppeLabels.get(k) ?? k}
                            </span>
                          ))}
                          {classes.length > 3 && (
                            <span className="self-end text-[10px] text-muted-foreground">
                              +{classes.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </Card>

        {selectedCamera && (
          <div className="grid grid-cols-2 gap-3">
            {!isMedicalView && (
              <Card featured className="col-span-2 p-4 text-center">
                <div
                  className={`text-3xl font-bold tabular-nums ${
                    compliance === undefined ? "text-muted-foreground" : "text-gradient"
                  }`}
                >
                  {compliance === undefined ? "—" : `${compliance}%`}
                </div>
                <div className="mt-1 text-[11px] font-bold text-muted-foreground">
                  نسبة الالتزام بالخوذة
                </div>
                {!selectedCamera.is_running && (
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    شغّل الكاميرا لعرض البيانات
                  </div>
                )}
                {selectedCamera.is_running &&
                  compliance === undefined &&
                  activeLiveStatus === "open" && (
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      لا يوجد أشخاص في الكادر الآن
                    </div>
                  )}
              </Card>
            )}
            {overlayMetrics.map((m) => (
              <SideMetric
                key={m.label}
                icon={sideMetricIcon(m.label)}
                value={m.value}
                label={m.label}
              />
            ))}
            {!isMedicalView && (
              <SideMetric
                icon={<Boxes className="size-4 text-primary" />}
                value={selectedCamera.is_running ? activeCounts.total : undefined}
                label="إجمالي الكشف"
              />
            )}
          </div>
        )}
      </div>

      <div className="min-h-[380px] lg:col-span-9 lg:h-full lg:min-h-0">
        <Card className="relative h-full w-full overflow-hidden border-border/80 bg-slate-950 p-0 shadow-xl">
          <LiveStage
            camera={selectedCamera}
            metrics={overlayMetrics}
            status={activeLiveStatus}
            compliance={compliance}
            skinHits={activeCounts.skin_hits}
            pending={camPending}
            canOperate={canOperate}
            onStart={() => selectedCamera && onToggleCamera(selectedCamera)}
            onStop={() => selectedCamera && onToggleCamera(selectedCamera)}
            onGoCameras={onGoCameras}
            onStreamReady={onStreamReady}
            onStreamLost={onStreamLost}
          />
        </Card>
      </div>
    </div>
  )
}
