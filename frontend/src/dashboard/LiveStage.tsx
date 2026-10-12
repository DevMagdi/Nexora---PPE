import { useState } from "react"
import type { ReactNode } from "react"
import {
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
import { cameraProfile, LIVE_STATUS_LABEL, PROFILE_LABEL, withParams } from "@/lib/formatters"
import Card from "@/shared/Card"
import EmptyState from "@/shared/EmptyState"
import ErrorState from "@/shared/ErrorState"
import LiveDot from "@/shared/LiveDot"
import type { Camera, LiveCounts, LiveMetricItem, LiveStatus } from "@/types"

function LiveMetric({ value, label }: { value: number | undefined; label: string }) {
  const animated = useCountUp(value)
  return (
    <div className="rounded-xl bg-white/10 px-3.5 py-2 ring-1 ring-white/15 backdrop-blur-md">
      <div className="text-base font-bold tabular-nums text-white">{animated ?? "—"}</div>
      <div className="mt-0.5 text-white/70">{label}</div>
    </div>
  )
}

function SideMetric({ icon, value, label }: { icon: ReactNode; value: number | undefined; label: string }) {
  const animated = useCountUp(value)
  return (
    <div className="card-premium flex flex-col items-center justify-center gap-1 rounded-xl border border-border/50 p-3.5">
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
      <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-8 text-center">
        <MonitorPlay className="mb-4 size-16 text-muted-foreground/20" />
        <h3 className="mb-2 text-xl font-bold">اختر كاميرا لبدء المراقبة</h3>
        <p className="mb-6 max-w-sm text-sm text-muted-foreground">
          اختر أحد المصادر من القائمة الجانبية لعرض البث المباشر والتحليل الذكي.
        </p>
        <Button type="button" variant="outline" onClick={onGoCameras} className="gap-2 rounded-xl">
          <CameraIcon className="size-4" /> إدارة الكاميرات
        </Button>
      </div>
    )
  }

  if (!camera.is_running) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-8 text-center">
        <WifiOff className="mb-4 size-16 text-destructive/20" />
        <h3 className="mb-2 text-xl font-bold">البث متوقف حاليًا</h3>
        <p className="mb-6 max-w-sm text-sm text-muted-foreground">
          {canOperate
            ? `«${camera.name}» لا تعمل الآن. يمكنك تشغيل البث والتحليل اللحظي.`
            : `«${camera.name}» لا تعمل الآن. اطلب من مدير النظام تشغيلها.`}
        </p>
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
      </div>
    )
  }

  const streamSrc = withParams(getMjpegStreamUrl(camera.id), nonce ? { r: String(nonce) } : {})
  const isMedical = cameraProfile(camera) === "medical"

  return (
    <>
      {streamError ? (
        <div className="flex h-full w-full flex-col items-center justify-center p-8 text-center">
          <AlertTriangle className="mb-4 size-14 text-warning/60" />
          <h3 className="mb-2 text-lg font-bold text-white">تعذّر الاتصال بالبث</h3>
          <p className="mb-6 max-w-sm text-sm text-white/60">
            الكاميرا تعمل لكن تدفق الفيديو لم يصل. تحقق من الشبكة أو أعد المحاولة.
          </p>
          <Button type="button" variant="outline" onClick={retry} className="gap-2 rounded-xl">
            <RefreshCw className="size-4" /> إعادة المحاولة
          </Button>
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
          className="absolute inset-0 z-0 h-full w-full object-contain"
          alt={`البث المباشر من ${camera.name}`}
        />
      )}

      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-[5] shadow-[inset_0_0_140px_rgba(0,0,0,0.5)]"
      />

      <div className="absolute inset-x-0 top-0 z-10 bg-gradient-to-b from-black/85 via-black/30 to-transparent p-6 pb-14">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2.5 truncate text-lg font-bold text-white drop-shadow-lg">
              <span
                className={`size-2.5 shrink-0 rounded-full ${
                  status === "open"
                    ? "bg-destructive animate-pulse shadow-[0_0_12px_rgba(239,68,68,0.7)]"
                    : "bg-warning"
                }`}
              />
              {camera.name}
            </h2>
            <p className="mt-1.5 text-xs text-white/60">
              المعرّف #{camera.id} · {PROFILE_LABEL[cameraProfile(camera)]} · المصدر {camera.source_type}
              {status !== "open" && status !== "idle" && (
                <span className="ms-2 text-warning">{LIVE_STATUS_LABEL[status]}</span>
              )}
            </p>
          </div>
          <Badge
            className={`shrink-0 border-none px-2.5 py-1 text-xs font-bold text-white backdrop-blur ${
              status === "open" ? "bg-red-600/95 live-ring" : "bg-amber-700/95"
            }`}
          >
            {status === "open" ? "مباشر" : LIVE_STATUS_LABEL[status] || "..."}
          </Badge>
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/95 via-black/50 to-transparent p-6 pt-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="grid grid-cols-4 gap-2.5 text-xs">
            {metrics.map((m) => (
              <LiveMetric key={m.label} value={m.value} label={m.label} />
            ))}
            {!isMedical && (
              <div className="rounded-xl bg-white/10 px-3.5 py-2 ring-1 ring-white/15 backdrop-blur-md">
                <div
                  className={`text-base font-bold tabular-nums ${
                    compliance === undefined
                      ? "text-white"
                      : compliance >= 90
                        ? "text-success"
                        : compliance >= 70
                          ? "text-warning"
                          : "text-destructive"
                  }`}
                >
                  {compliance === undefined ? "—" : `${compliance}%`}
                </div>
                <div className="mt-0.5 text-white/70">التزام</div>
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
              className="gap-2 rounded-xl shadow-xl shadow-destructive/30"
            >
              {pending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Square size={14} fill="currentColor" />
              )}{" "}
              إيقاف البث
            </Button>
          )}
        </div>
      </div>
    </>
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
    <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 lg:h-[calc(100dvh-8rem)] lg:grid-cols-12">
      <div className="flex flex-col gap-4 lg:col-span-3 lg:h-full lg:min-h-0">
        <Card className="flex max-h-[45vh] flex-1 flex-col overflow-hidden p-4 lg:max-h-none">
          <div className="relative mb-4">
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
              <div className="py-10 text-center text-sm text-muted-foreground">
                <Loader2 className="mx-auto mb-2 size-4 animate-spin" />
                جارٍ تحميل الكاميرات...
              </div>
            ) : cameraList.length === 0 ? (
              <EmptyState
                compact
                icon={<CameraIcon className="size-6 text-primary" />}
                title="لا توجد كاميرات بعد"
                desc="اربط أول كاميرا وابدأ المراقبة الذكية خلال دقيقة."
                action={
                  <button type="button" className="btn-cta text-sm" onClick={onAddFirstCamera}>
                    <Plus className="size-4" /> أضف أول كاميرا
                  </button>
                }
              />
            ) : filteredCams.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted-foreground">لا توجد نتائج للبحث</div>
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
                    className={`group flex w-full items-start gap-3 rounded-xl border p-3.5 text-start transition-colors ${
                      isSelected
                        ? "border-primary/30 bg-primary/12 shadow-md shadow-primary/5"
                        : "border-transparent hover:bg-muted/40"
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
                          className={`shrink-0 text-[11px] font-bold ${
                            c.is_running ? "text-success-foreground" : "text-muted-foreground"
                          }`}
                        >
                          {c.is_running ? "تعمل" : "متوقفة"}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="rounded border border-border/40 bg-card px-1.5 py-0.5 tabular-nums">
                          #{c.id}
                        </span>
                        <span className="truncate">
                          {PROFILE_LABEL[cameraProfile(c)]} · {c.source_type}
                        </span>
                      </div>
                      {classes.length > 0 && (
                        <div className="mt-2.5 flex flex-wrap gap-1">
                          {classes.slice(0, 3).map((k) => (
                            <span
                              key={k}
                              className="rounded-md border border-border/20 bg-secondary/50 px-1.5 py-0.5 text-[9px] font-medium text-secondary-foreground"
                            >
                              {ppeLabels.get(k) ?? k}
                            </span>
                          ))}
                          {classes.length > 3 && (
                            <span className="self-end text-[9px] text-muted-foreground">
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
              <SideMetric key={m.label} icon={sideMetricIcon(m.label)} value={m.value} label={m.label} />
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

      <div className="min-h-[360px] lg:col-span-9 lg:h-full lg:min-h-0">
        <Card className="relative aspect-video h-full overflow-hidden bg-black p-0 shadow-2xl shadow-black/30 lg:aspect-auto">
          <LiveStage
            camera={selectedCamera}
            metrics={overlayMetrics}
            status={activeLiveStatus}
            compliance={compliance}
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
