import { useMemo, useState } from "react"
import { Camera as CameraIcon, Cctv, Plus, Search } from "lucide-react"
import AddCameraForm from "@/cameras/AddCameraForm"
import CameraCard from "@/cameras/CameraCard"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { cameraProfile, MAX_GRID_PREVIEWS } from "@/lib/formatters"
import EmptyState from "@/shared/EmptyState"
import ErrorState from "@/shared/ErrorState"
import PageHeader from "@/shared/PageHeader"
import SkeletonBlock from "@/shared/SkeletonBlock"
import type { Camera } from "@/types"

type StatusFilter = "all" | "running" | "stopped"
type ProfileFilter = "all" | "construction" | "medical"

interface CameraGridProps {
  cameraList: Camera[]
  orderedCams: Camera[]
  runningCount: number
  camerasLoading: boolean
  camerasError: boolean
  onRetryCameras: () => void
  canOperate: boolean
  addOpen: boolean
  onAddOpenChange: (open: boolean) => void
  onAddSuccess: () => void
  ppeLabels: Map<string, string>
  previewAllowed: Set<number>
  togglingCamId: number | null
  deletingCamId: number | null
  alertsByCam: Map<number, number>
  onToggleCamera: (cam: Camera) => void
  onSelectCam: (id: number) => void
  onOpenEdit: (cam: Camera) => void
  onAskDelete: (cam: Camera) => void
}

export default function CameraGrid({
  cameraList,
  orderedCams,
  runningCount,
  camerasLoading,
  camerasError,
  onRetryCameras,
  canOperate,
  addOpen,
  onAddOpenChange,
  onAddSuccess,
  ppeLabels,
  previewAllowed,
  togglingCamId,
  deletingCamId,
  alertsByCam,
  onToggleCamera,
  onSelectCam,
  onOpenEdit,
  onAskDelete,
}: CameraGridProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [profileFilter, setProfileFilter] = useState<ProfileFilter>("all")
  const [searchQuery, setSearchQuery] = useState("")

  const visibleCams = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return orderedCams.filter((c) => {
      if (statusFilter === "running" && !c.is_running) return false
      if (statusFilter === "stopped" && c.is_running) return false
      if (profileFilter !== "all" && cameraProfile(c) !== profileFilter) return false
      if (q && !c.name.toLowerCase().includes(q) && !String(c.id).includes(q)) return false
      return true
    })
  }, [orderedCams, statusFilter, profileFilter, searchQuery])

  const stoppedCount = cameraList.length - runningCount

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        icon={<Cctv className="size-5" />}
        title="إدارة مصادر الفيديو والكاميرات"
        subtitle={
          runningCount > MAX_GRID_PREVIEWS
            ? `اربط كاميرات RTSP أو مصادر الفيديو وتحكم في تشغيلها (تُعرض معاينة حية لأول ${MAX_GRID_PREVIEWS} كاميرات للحفاظ على الأداء).`
            : "اربط كاميرات RTSP أو مصادر الفيديو وتحكم في تشغيلها وقواعد الرصد من مكان واحد."
        }
        badge={
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-light px-3 py-1 text-xs font-bold text-primary">
            {runningCount} نشطة من {cameraList.length}
          </span>
        }
        actions={
          canOperate ? (
            <Dialog open={addOpen} onOpenChange={onAddOpenChange}>
              <button type="button" className="btn-cta" onClick={() => onAddOpenChange(true)}>
                <Plus className="size-4" /> إضافة كاميرا جديدة
              </button>
              <DialogContent className="max-w-lg rounded-2xl border-border bg-card">
                <DialogHeader>
                  <DialogTitle className="font-bold text-foreground">
                    ربط كاميرا جديدة بالنظام
                  </DialogTitle>
                  <DialogDescription>
                    أدخل رابط المصدر واختر معدات الوقاية المطلوب رصدها.
                  </DialogDescription>
                </DialogHeader>
                <AddCameraForm onSuccess={onAddSuccess} />
              </DialogContent>
            </Dialog>
          ) : undefined
        }
      />

      {cameraList.length > 0 && (
        <div className="card-premium flex flex-col justify-between gap-3 border border-border/70 p-4 sm:flex-row sm:items-center">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setStatusFilter("all")}
              className={`chip-filter ${statusFilter === "all" ? "chip-filter-active" : ""}`}
            >
              الكل ({cameraList.length})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("running")}
              className={`chip-filter ${statusFilter === "running" ? "chip-filter-active" : ""}`}
            >
              تعمل الآن ({runningCount})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("stopped")}
              className={`chip-filter ${statusFilter === "stopped" ? "chip-filter-active" : ""}`}
            >
              متوقفة ({stoppedCount})
            </button>

            <div className="mx-1 hidden h-4 w-px bg-border sm:block" />

            <button
              type="button"
              onClick={() =>
                setProfileFilter((p) => (p === "construction" ? "all" : "construction"))
              }
              className={`chip-filter ${
                profileFilter === "construction" ? "chip-filter-active" : ""
              }`}
            >
              إنشاءات
            </button>
            <button
              type="button"
              onClick={() => setProfileFilter((p) => (p === "medical" ? "all" : "medical"))}
              className={`chip-filter ${profileFilter === "medical" ? "chip-filter-active" : ""}`}
            >
              طبي
            </button>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="بحث باسم الكاميرا أو المعرّف..."
              aria-label="بحث في الكاميرات"
              className="h-9 rounded-xl pe-9 text-xs"
            />
          </div>
        </div>
      )}

      {camerasError && cameraList.length === 0 ? (
        <ErrorState title="تعذّر تحميل الكاميرات" onRetry={onRetryCameras} />
      ) : camerasLoading && cameraList.length === 0 ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div
              key={i}
              className="card-premium overflow-hidden rounded-2xl border border-border/60"
            >
              <SkeletonBlock className="h-44 w-full rounded-none" />
              <div className="space-y-3 p-5">
                <SkeletonBlock className="h-4 w-2/3 rounded" />
                <SkeletonBlock className="h-3 w-full rounded" />
                <SkeletonBlock className="h-10 w-full rounded-xl" />
              </div>
            </div>
          ))}
        </div>
      ) : cameraList.length === 0 ? (
        <EmptyState
          icon={<CameraIcon className="size-6 text-primary" />}
          title="ابدأ بربط أول كاميرا"
          desc="أضف رابط RTSP أو مصدر فيديو، وسيبدأ النظام في رصد مخالفات معدات الوقاية تلقائيًا."
          action={
            canOperate ? (
              <button type="button" className="btn-cta" onClick={() => onAddOpenChange(true)}>
                <Plus className="size-4" /> أضف أول كاميرا خلال دقيقة
              </button>
            ) : undefined
          }
        />
      ) : visibleCams.length === 0 ? (
        <EmptyState
          compact
          icon={<CameraIcon className="size-6 text-muted-foreground" />}
          title="لا توجد كاميرات مطابقة للفلتر"
          desc="جرّب إزالة الفلاتر أو البحث بكلمة أخرى."
        />
      ) : (
        <div className="stagger grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {visibleCams.map((c) => (
            <CameraCard
              key={c.id}
              camera={c}
              ppeLabels={ppeLabels}
              allowStream={previewAllowed.has(c.id)}
              canOperate={canOperate}
              pending={togglingCamId === c.id}
              deletePending={deletingCamId === c.id}
              alerts={alertsByCam.get(c.id) ?? 0}
              onToggle={() => onToggleCamera(c)}
              onWatch={() => onSelectCam(c.id)}
              onEdit={() => onOpenEdit(c)}
              onDelete={() => onAskDelete(c)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
