import { useState } from "react"
import { Camera as CameraIcon, Loader2, MonitorPlay, Pencil, Play, Square, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getMjpegStreamUrl } from "@/lib/api"
import { cameraProfile, maskUri, PROFILE_LABEL } from "@/lib/domain"
import { useInView } from "@/hooks/useInView"
import type { Camera } from "@/types"
import { PremiumCard } from "@/shared/PremiumCard"

export interface CameraCardProps {
  camera: Camera
  ppeLabels: Map<string, string>
  allowStream: boolean
  canOperate: boolean
  pending: boolean
  deletePending: boolean
  alerts: number
  onToggle: () => void
  onWatch: () => void
  onEdit: () => void
  onDelete: () => void
}

export function CameraCard({ camera, ppeLabels, allowStream, canOperate, pending, deletePending, alerts, onToggle, onWatch, onEdit, onDelete }: CameraCardProps) {
  const [ref, inView] = useInView<HTMLDivElement>()
  const [failedPreviewKey, setFailedPreviewKey] = useState<string | null>(null)
  const previewKey = `${camera.id}-${camera.is_running}-${allowStream}`
  const previewError = failedPreviewKey === previewKey
  const showStream = camera.is_running && allowStream && inView && !previewError
  const classes = camera.enabled_classes ?? []

  return (
    <div ref={ref} className="h-full">
      <PremiumCard className="group flex h-full flex-col overflow-hidden transition-transform duration-200 hover:-translate-y-0.5">
        <div className="relative h-44 shrink-0 overflow-hidden bg-slate-950">
          {showStream ? (
            <img
              src={getMjpegStreamUrl(camera.id)}
              loading="lazy"
              className="h-full w-full object-cover opacity-85 transition-opacity duration-300 group-hover:opacity-100"
              alt={`معاينة ${camera.name}`}
              onError={() => setFailedPreviewKey(previewKey)}
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-slate-950 to-slate-800 text-white/55">
              <CameraIcon className="size-9 opacity-55" />
              <span className="text-xs font-medium">{camera.is_running ? previewError ? "المعاينة غير متاحة" : "تعمل · اضغط للمشاهدة" : "متوقفة"}</span>
            </div>
          )}

          <div className="absolute end-3 top-3 rounded-lg border border-white/10 bg-black/65 px-2 py-1 text-[11px] tabular-nums text-white backdrop-blur-md">#{camera.id}</div>
          <div className={`absolute start-3 top-3 flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold text-white shadow-sm ${!camera.is_running ? "bg-slate-600/90" : alerts > 0 ? "bg-red-600/95" : "bg-emerald-700/95"}`}>
            <span className={`size-1.5 rounded-full bg-white ${camera.is_running ? "animate-pulse" : "opacity-60"}`} />
            {!camera.is_running ? "متوقفة" : alerts > 0 ? `${alerts} تنبيه` : "تعمل"}
          </div>
        </div>

        <div className="flex flex-1 flex-col p-4 sm:p-5">
          <div className="mb-3 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="min-w-0 truncate text-base font-bold text-foreground transition-colors group-hover:text-primary">{camera.name}</h3>
              <Badge variant="secondary" className="shrink-0 rounded-md px-2 text-[10px]">{PROFILE_LABEL[cameraProfile(camera)]}</Badge>
            </div>
            <div dir="ltr" className="mt-2 max-w-full truncate rounded-lg bg-muted/60 px-2.5 py-1.5 text-start text-[11px] text-muted-foreground" title="تم إخفاء بيانات الدخول">{maskUri(camera.source_uri)}</div>
          </div>

          <div className="mb-4 flex min-h-7 flex-wrap gap-1.5">
            {classes.slice(0, 4).map((key) => (
              <Badge key={key} variant="outline" className="rounded-md border-border/70 bg-muted/30 text-[11px] font-medium">{ppeLabels.get(key) ?? key}</Badge>
            ))}
            {classes.length > 4 && <span className="self-center text-[11px] text-muted-foreground">+{classes.length - 4}</span>}
            {classes.length === 0 && <span className="text-[11px] italic text-muted-foreground">لم يتم تحديد فئات</span>}
          </div>

          <div className="mt-auto flex items-center gap-1.5 border-t border-border/70 pt-3">
            {canOperate && (
              <Button type="button" size="sm" variant={camera.is_running ? "destructive" : "default"} onClick={onToggle} disabled={pending || deletePending} className="min-h-11 flex-1 gap-1.5 rounded-xl text-xs font-bold">
                {pending ? <Loader2 className="size-4 animate-spin" /> : camera.is_running ? <Square className="size-3 fill-current" /> : <Play className="size-3 fill-current" />}
                {camera.is_running ? "إيقاف" : "تشغيل"}
              </Button>
            )}
            <Button type="button" size="icon" variant="ghost" aria-label={`مشاهدة ${camera.name}`} onClick={onWatch} disabled={deletePending} className="tap-target shrink-0 rounded-xl text-muted-foreground hover:bg-primary-light hover:text-primary">
              <MonitorPlay className="size-4" />
            </Button>
            {canOperate && (
              <>
                <Button type="button" size="icon" variant="ghost" aria-label={`تعديل ${camera.name}`} onClick={onEdit} disabled={deletePending} className="tap-target shrink-0 rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground">
                  <Pencil className="size-4" />
                </Button>
                <Button type="button" size="icon" variant="ghost" aria-label={`حذف ${camera.name}`} onClick={onDelete} disabled={deletePending} className="tap-target shrink-0 rounded-xl text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
                  {deletePending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                </Button>
              </>
            )}
          </div>
        </div>
      </PremiumCard>
    </div>
  )
}
