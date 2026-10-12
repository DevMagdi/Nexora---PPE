import { Camera as CameraIcon, Plus } from "lucide-react"
import AddCameraForm from "@/cameras/AddCameraForm"
import CameraCard from "@/cameras/CameraCard"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { MAX_GRID_PREVIEWS } from "@/lib/formatters"
import EmptyState from "@/shared/EmptyState"
import ErrorState from "@/shared/ErrorState"
import SkeletonBlock from "@/shared/SkeletonBlock"
import type { Camera } from "@/types"

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
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="card-premium flex flex-col justify-between gap-4 rounded-2xl border border-border/60 p-6 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-bold text-foreground">إدارة مصادر الفيديو</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">
            اربط كاميرات RTSP وتحكم في تشغيلها وإيقافها من مكان واحد.
          </p>
          {runningCount > MAX_GRID_PREVIEWS && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              تُعرض معاينة حية لأول {MAX_GRID_PREVIEWS} كاميرات فقط للحفاظ على الأداء.
            </p>
          )}
        </div>

        {canOperate && (
          <Dialog open={addOpen} onOpenChange={onAddOpenChange}>
            <button type="button" className="btn-cta" onClick={() => onAddOpenChange(true)}>
              <Plus className="size-4" /> إضافة كاميرا جديدة
            </button>
            <DialogContent className="max-w-lg rounded-2xl border-border bg-card">
              <DialogHeader>
                <DialogTitle className="font-bold text-foreground">ربط كاميرا جديدة بالنظام</DialogTitle>
                <DialogDescription>
                  أدخل رابط المصدر واختر معدات الوقاية المطلوب رصدها.
                </DialogDescription>
              </DialogHeader>
              <AddCameraForm onSuccess={onAddSuccess} />
            </DialogContent>
          </Dialog>
        )}
      </div>

      {camerasError && cameraList.length === 0 ? (
        <ErrorState title="تعذّر تحميل الكاميرات" onRetry={onRetryCameras} />
      ) : camerasLoading && cameraList.length === 0 ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="card-premium overflow-hidden rounded-2xl border border-border/60">
              <SkeletonBlock className="h-44 w-full rounded-none" />
              <div className="space-y-3 p-5">
                <SkeletonBlock className="h-4 w-2/3 rounded" />
                <SkeletonBlock className="h-3 w-full rounded" />
                <SkeletonBlock className="h-8 w-full rounded-xl" />
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
      ) : (
        <div className="stagger grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {orderedCams.map((c) => (
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
