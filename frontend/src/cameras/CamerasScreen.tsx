import { useMemo, useState } from "react"
import { Camera as CameraIcon, Loader2, Plus, Search } from "lucide-react"
import AddCameraForm from "@/components/AddCameraForm"
import ConfirmDialog from "@/components/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useDeleteCamera } from "@/hooks/useNexora"
import { getErrorMessage } from "@/lib/utils"
import { CameraCard } from "@/cameras/CameraCard"
import { EmptyState } from "@/shared/EmptyState"
import { ErrorState } from "@/shared/ErrorState"
import { PageHeader } from "@/shared/PageHeader"
import type { Camera } from "@/types"
import type { ToastState } from "@/types/app"

type Props = {
  cameras: Camera[]
  orderedCameras: Camera[]
  camerasLoading: boolean
  camerasError: boolean
  canOperate: boolean
  ppeLabels: Map<string, string>
  previewAllowed: Set<number>
  togglingCameraId: number | null
  alertsByCamera: Map<number, number>
  onRetry: () => void
  onToggle: (camera: Camera) => void
  onWatch: (camera: Camera) => void
  onDeleted: (camera: Camera) => void
  notify: (tone: ToastState["tone"], text: string) => void
}

export function CamerasScreen({ cameras, orderedCameras, camerasLoading, camerasError, canOperate, ppeLabels, previewAllowed, togglingCameraId, alertsByCamera, onRetry, onToggle, onWatch, onDeleted, notify }: Props) {
  const deleteMutation = useDeleteCamera()
  const [search, setSearch] = useState("")
  const [addOpen, setAddOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null)

  const filteredCameras = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    if (!query) return orderedCameras
    return orderedCameras.filter((camera) => `${camera.name} ${camera.id} ${camera.profile} ${camera.source_type}`.toLocaleLowerCase().includes(query))
  }, [orderedCameras, search])
  const runningCount = cameras.filter((camera) => camera.is_running).length
  const pendingDeleteId = deleteMutation.isPending ? deleteMutation.variables : undefined

  const deleteCamera = () => {
    if (!deleteTarget) return
    const target = deleteTarget
    deleteMutation.mutate(target.id, {
      onSuccess: () => {
        setDeleteTarget(null)
        onDeleted(target)
        notify("success", `تم حذف «${target.name}»`)
      },
      onError: (error) => notify("error", getErrorMessage(error, `تعذّر حذف «${target.name}»`)),
    })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        eyebrow="إدارة الأجهزة"
        title="مصادر الفيديو"
        description={`تحكم في الكاميرات ومصادر التحليل. ${runningCount} من ${cameras.length} كاميرا تعمل الآن.`}
        action={canOperate ? (
          <Dialog open={addOpen} onOpenChange={setAddOpen}>
            <Button type="button" onClick={() => setAddOpen(true)} className="min-h-11 gap-2 rounded-xl px-5">
              <Plus className="size-4" /> إضافة كاميرا
            </Button>
            <DialogContent className="max-h-[90dvh] max-w-lg overflow-y-auto rounded-2xl border-border bg-card">
              <DialogHeader>
                <DialogTitle className="font-bold text-foreground">ربط كاميرا جديدة</DialogTitle>
                <DialogDescription>ابدأ باختيار المصدر، ثم حدّد معدات الوقاية التي تريد مراقبتها.</DialogDescription>
              </DialogHeader>
              <AddCameraForm onSuccess={() => { setAddOpen(false); notify("success", "تمت إضافة الكاميرا بنجاح") }} />
            </DialogContent>
          </Dialog>
        ) : undefined}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-sm">
          <Search className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ابحث بالاسم أو الرقم..." aria-label="البحث في الكاميرات" className="min-h-11 rounded-xl bg-card pe-10" />
        </div>
        {runningCount > 4 && <p className="text-xs text-muted-foreground">تُعرض معاينة حية لأول 4 كاميرات فقط للحفاظ على الأداء.</p>}
      </div>

      {camerasError && cameras.length === 0 ? (
        <ErrorState title="تعذّر تحميل الكاميرات" onRetry={onRetry} />
      ) : camerasLoading && cameras.length === 0 ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4" aria-label="جارٍ تحميل الكاميرات">
          {Array.from({ length: 4 }, (_, index) => <CameraSkeleton key={index} />)}
        </div>
      ) : cameras.length === 0 ? (
        <EmptyState
          icon={<CameraIcon className="size-6 text-primary" />}
          title="ابدأ بإضافة أول كاميرا"
          desc="اربط كاميرا ويب أو بث RTSP أو ملف فيديو مسموحًا، ثم اختر قواعد معدات الوقاية المناسبة."
          action={canOperate ? <Button type="button" onClick={() => setAddOpen(true)} className="min-h-11 gap-2 rounded-xl"><Plus className="size-4" /> إضافة كاميرا</Button> : undefined}
        />
      ) : filteredCameras.length === 0 ? (
        <EmptyState icon={<Search className="size-6 text-muted-foreground" />} title="لا توجد نتائج" desc="جرّب كلمة بحث أو رقم كاميرا مختلفًا." compact />
      ) : (
        <div className="stagger grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {filteredCameras.map((camera) => (
            <CameraCard
              key={camera.id}
              camera={camera}
              ppeLabels={ppeLabels}
              allowStream={previewAllowed.has(camera.id)}
              canOperate={canOperate}
              pending={togglingCameraId === camera.id}
              deletePending={pendingDeleteId === camera.id}
              alerts={alertsByCamera.get(camera.id) ?? 0}
              onToggle={() => onToggle(camera)}
              onWatch={() => onWatch(camera)}
              onEdit={() => setEditingCamera(camera)}
              onDelete={() => setDeleteTarget(camera)}
            />
          ))}
        </div>
      )}

      <Dialog open={editingCamera !== null} onOpenChange={(open) => { if (!open) setEditingCamera(null) }}>
        <DialogContent className="max-h-[90dvh] max-w-lg overflow-y-auto rounded-2xl border-border bg-card">
          <DialogHeader>
            <DialogTitle className="font-bold text-foreground">تعديل إعدادات الكاميرا</DialogTitle>
            <DialogDescription>حدّث الاسم أو المصدر أو قواعد معدات الوقاية. بيانات الدخول في المصدر مخفية في البطاقات.</DialogDescription>
          </DialogHeader>
          {editingCamera && <AddCameraForm key={editingCamera.id} mode="edit" camera={editingCamera} onSuccess={() => { setEditingCamera(null); notify("success", "تم تحديث الكاميرا بنجاح") }} />}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="تأكيد حذف الكاميرا"
        description={deleteTarget ? `هل أنت متأكد أنك تريد حذف «${deleteTarget.name}»؟` : undefined}
        confirmLabel="حذف الكاميرا"
        cancelLabel="إلغاء"
        tone="destructive"
        pending={deleteMutation.isPending}
        onCancel={() => { if (!deleteMutation.isPending) setDeleteTarget(null) }}
        onConfirm={deleteCamera}
      />
    </div>
  )
}

function CameraSkeleton() {
  return (
    <div className="card-premium overflow-hidden rounded-2xl border border-border/70 bg-card">
      <div className="skeleton-shimmer h-44" />
      <div className="space-y-3 p-5">
        <div className="skeleton-shimmer h-4 w-2/3 rounded" />
        <div className="skeleton-shimmer h-3 w-full rounded" />
        <div className="skeleton-shimmer h-10 w-full rounded-xl" />
      </div>
      <span className="sr-only"><Loader2 className="size-4 animate-spin" /> جارٍ التحميل</span>
    </div>
  )
}
