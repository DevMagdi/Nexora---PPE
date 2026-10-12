import { useMemo, useState } from "react"
import { Boxes, Camera as CameraIcon, Eye, HardHat, Search, ShieldAlert, Shirt, Users } from "lucide-react"
import { Input } from "@/components/ui/input"
import { cameraProfile, liveMetrics, PROFILE_LABEL } from "@/lib/domain"
import type { Camera } from "@/types"
import type { LiveCounts, LiveStatus } from "@/types/app"
import { EmptyState } from "@/shared/EmptyState"
import { ErrorState } from "@/shared/ErrorState"
import { LiveDot } from "@/shared/LiveDot"
import { PageHeader } from "@/shared/PageHeader"
import { PremiumCard } from "@/shared/PremiumCard"
import { SideMetric } from "@/dashboard/SideMetric"
import { LiveStage } from "@/dashboard/LiveStage"

const sideMetricIcon = (label: string) => {
  if (label === "أشخاص") return <Users className="size-4 text-info" />
  if (label === "خوذات") return <HardHat className="size-4 text-warning" />
  if (label === "سترات") return <Shirt className="size-4 text-highlight" />
  if (label === "إجمالي الكشف") return <Boxes className="size-4 text-primary" />
  if (label.includes("نظارات")) return <Eye className="size-4 text-warning" />
  if (label.includes("كمامة") || label.includes("قفاز")) return <ShieldAlert className="size-4 text-destructive" />
  if (label.includes("غطاء")) return <HardHat className="size-4 text-warning" />
  return <Boxes className="size-4 text-primary" />
}

type Props = {
  cameras: Camera[]
  camerasLoading: boolean
  camerasError: boolean
  selectedCamera: Camera | null
  ppeLabels: Map<string, string>
  counts: LiveCounts
  status: LiveStatus
  compliance: number | undefined
  canOperate: boolean
  pending: boolean
  onRetryCameras: () => void
  onSelectCamera: (id: number) => void
  onStart: () => void
  onStop: () => void
  onGoCameras: () => void
  onStreamReady: () => void
  onStreamLost: () => void
}

export function LiveScreen({ cameras, camerasLoading, camerasError, selectedCamera, ppeLabels, counts, status, compliance, canOperate, pending, onRetryCameras, onSelectCamera, onStart, onStop, onGoCameras, onStreamReady, onStreamLost }: Props) {
  const [search, setSearch] = useState("")
  const activeProfile = selectedCamera ? cameraProfile(selectedCamera) : "construction"
  const isMedical = activeProfile === "medical"
  const metrics = liveMetrics(activeProfile, selectedCamera?.is_running ? counts : {})
  const medicalNegatives = (counts.no_mask ?? 0) + (counts.no_gloves ?? 0) + (counts.no_goggles ?? 0) + (counts.no_cap ?? 0)
  const filteredCameras = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    if (!query) return cameras
    return cameras.filter((camera) => `${camera.name} ${camera.id}`.toLocaleLowerCase().includes(query))
  }, [cameras, search])

  return (
    <div className="mx-auto max-w-[1480px] space-y-5">
      <PageHeader eyebrow="مركز العمليات" title="المراقبة المباشرة" description={selectedCamera ? `متابعة ${selectedCamera.name} وتحليل الالتزام لحظيًا.` : "اختر كاميرا لمشاهدة البث ومؤشرات التحليل."} className="hidden sm:flex" />

      <div className="grid grid-cols-1 gap-5 lg:h-[calc(100dvh-11rem)] lg:grid-cols-12">
        <section aria-label="بث الكاميرا" className="order-1 min-h-[320px] lg:order-2 lg:col-span-9 lg:min-h-0">
          <PremiumCard className="relative h-[min(68vh,760px)] min-h-[320px] overflow-hidden bg-black p-0 shadow-floating lg:h-full">
            <LiveStage
              camera={selectedCamera}
              status={status}
              pending={pending}
              canOperate={canOperate}
              onStart={onStart}
              onStop={onStop}
              onGoCameras={onGoCameras}
              onStreamReady={onStreamReady}
              onStreamLost={onStreamLost}
            />
          </PremiumCard>
        </section>

        <aside aria-label="اختيار الكاميرا ومؤشرات البث" className="order-2 flex min-h-0 flex-col gap-4 lg:order-1 lg:col-span-3">
          <PremiumCard className="flex max-h-[38vh] min-h-48 flex-1 flex-col overflow-hidden p-3.5 sm:p-4 lg:max-h-none">
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="بحث بالاسم أو الرقم..." aria-label="بحث عن كاميرا" className="min-h-11 rounded-xl bg-muted/40 pe-10" />
            </div>
            <div className="flex-1 space-y-1.5 overflow-y-auto pe-1">
              {camerasError && cameras.length === 0 ? (
                <ErrorState compact title="تعذّر تحميل الكاميرات" onRetry={onRetryCameras} />
              ) : camerasLoading && cameras.length === 0 ? (
                <div className="space-y-3 p-3" aria-label="جارٍ تحميل الكاميرات">
                  {Array.from({ length: 3 }, (_, index) => <div key={index} className="skeleton-shimmer h-14 rounded-xl" />)}
                </div>
              ) : cameras.length === 0 ? (
                <EmptyState compact icon={<CameraIcon className="size-5 text-primary" />} title="لا توجد كاميرات بعد" desc="اربط أول كاميرا للبدء بالمراقبة." />
              ) : filteredCameras.length === 0 ? (
                <EmptyState compact icon={<Search className="size-5 text-muted-foreground" />} title="لا توجد نتائج" desc="جرّب اسمًا أو رقمًا آخر." />
              ) : (
                filteredCameras.map((camera) => {
                  const isSelected = selectedCamera?.id === camera.id
                  const classes = camera.enabled_classes ?? []
                  return (
                    <button
                      key={camera.id}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => onSelectCamera(camera.id)}
                      className={`group flex min-h-14 w-full items-start gap-3 rounded-xl border p-3 text-start transition-colors ${isSelected ? "border-primary/35 bg-primary-light" : "border-transparent hover:bg-muted/55"}`}
                    >
                      <span className="mt-1.5"><LiveDot tone="success" active={camera.is_running} /></span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-bold text-foreground group-hover:text-primary">{camera.name}</span>
                          <span className={`shrink-0 text-[11px] font-semibold ${camera.is_running ? "text-success-foreground" : "text-muted-foreground"}`}>{camera.is_running ? "تعمل" : "متوقفة"}</span>
                        </span>
                        <span className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                          <span className="rounded-md border border-border/50 bg-card px-1.5 py-0.5 tabular-nums">#{camera.id}</span>
                          <span className="truncate">{PROFILE_LABEL[cameraProfile(camera)]} · {camera.source_type}</span>
                        </span>
                        {classes.length > 0 && <span className="mt-2 flex flex-wrap gap-1">{classes.slice(0, 3).map((key) => <span key={key} className="rounded-md bg-secondary/70 px-1.5 py-0.5 text-[10px] text-secondary-foreground">{ppeLabels.get(key) ?? key}</span>)}{classes.length > 3 && <span className="self-end text-[10px] text-muted-foreground">+{classes.length - 3}</span>}</span>}
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </PremiumCard>

          {selectedCamera && (
            <div className="grid grid-cols-2 gap-2.5 sm:gap-3">
              {!isMedical && (
                <PremiumCard featured className="col-span-2 p-3.5 text-center">
                  <div className={`text-3xl font-bold tabular-nums ${compliance === undefined ? "text-muted-foreground" : "text-gradient"}`}>{compliance === undefined ? "—" : `${compliance}%`}</div>
                  <div className="mt-1 text-[11px] font-semibold text-muted-foreground">نسبة الالتزام بالخوذة</div>
                  {!selectedCamera.is_running && <div className="mt-1 text-[11px] text-muted-foreground">شغّل الكاميرا لعرض المؤشرات</div>}
                  {selectedCamera.is_running && compliance === undefined && status === "open" && <div className="mt-1 text-[11px] text-muted-foreground">لا يوجد أشخاص في الكادر الآن</div>}
                </PremiumCard>
              )}
              {metrics.map((metric) => <SideMetric key={metric.label} icon={sideMetricIcon(metric.label)} value={metric.value} label={metric.label} />)}
              {!isMedical && <SideMetric icon={<Boxes className="size-4 text-primary" />} value={selectedCamera.is_running ? counts.total : undefined} label="إجمالي الكشف" />}
              {isMedical && <PremiumCard className="col-span-2 flex items-center justify-between gap-3 p-3.5 text-sm"><span className="font-semibold text-muted-foreground">مخالفات ظاهرة الآن</span><span className="font-bold tabular-nums text-foreground">{selectedCamera.is_running ? medicalNegatives : "—"}</span></PremiumCard>}
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
