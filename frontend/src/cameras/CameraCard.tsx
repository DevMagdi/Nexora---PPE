import { Camera as CameraIcon, Loader2, MonitorPlay, Pencil, Play, Square, Trash2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useInView } from "@/hooks/useUiHooks"
import { getMjpegStreamUrl } from "@/lib/api"
import { cameraProfile, maskUri, PROFILE_LABEL } from "@/lib/formatters"
import Card from "@/shared/Card"
import type { Camera } from "@/types"

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

export default function CameraCard({
  camera,
  ppeLabels,
  allowStream,
  canOperate,
  pending,
  deletePending,
  alerts,
  onToggle,
  onWatch,
  onEdit,
  onDelete,
}: CameraCardProps) {
  const [ref, inView] = useInView<HTMLDivElement>()
  const showStream = camera.is_running && allowStream && inView
  const classes = camera.enabled_classes ?? []

  return (
    <div ref={ref} className="h-full">
      <Card className="group flex h-full flex-col overflow-hidden">
        <div className="relative h-44 shrink-0 overflow-hidden bg-black">
          {showStream ? (
            <img
              src={getMjpegStreamUrl(camera.id)}
              loading="lazy"
              className="h-full w-full object-cover opacity-80 transition-all duration-700 group-hover:scale-105 group-hover:opacity-100"
              alt={`معاينة ${camera.name}`}
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center bg-secondary/20 text-muted-foreground">
              {camera.is_running ? (
                <MonitorPlay className="mb-2 size-10 opacity-25" />
              ) : (
                <CameraIcon className="mb-2 size-10 opacity-25" />
              )}
              <span className="text-xs font-medium opacity-60">
                {camera.is_running ? "تعمل · اضغط للمشاهدة" : "متوقفة"}
              </span>
            </div>
          )}

          <div className="absolute end-3 top-3 rounded-lg border border-white/10 bg-black/70 px-2 py-1 text-[11px] tabular-nums text-white backdrop-blur-md">
            #{camera.id}
          </div>
          <div
            className={`absolute start-3 top-3 flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold text-white shadow-sm ${
              !camera.is_running ? "bg-slate-600/90" : alerts > 0 ? "bg-red-600/95" : "bg-emerald-700/95"
            }`}
          >
            <span
              className={`size-1.5 rounded-full bg-white ${
                camera.is_running ? "animate-pulse" : "opacity-60"
              }`}
            />
            {!camera.is_running ? "متوقفة" : alerts > 0 ? `${alerts} تنبيه` : "تعمل"}
          </div>
        </div>

        <div className="flex flex-1 flex-col p-5">
          <div className="mb-3">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-base font-bold text-foreground transition-colors group-hover:text-primary">
                {camera.name}
              </h3>
              <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-bold text-muted-foreground">
                {PROFILE_LABEL[cameraProfile(camera)]}
              </span>
            </div>
            <div
              dir="ltr"
              className="mt-1.5 inline-block max-w-full truncate rounded-lg bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground"
              title="تم إخفاء بيانات الدخول"
            >
              {maskUri(camera.source_uri)}
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-1.5">
            {classes.map((k) => (
              <Badge
                key={k}
                variant="outline"
                className="rounded-md border-border/40 bg-muted/40 text-[11px] font-medium text-foreground/70"
              >
                {ppeLabels.get(k) ?? k}
              </Badge>
            ))}
            {classes.length === 0 && (
              <span className="text-[11px] italic text-muted-foreground">لم يتم تحديد فئات</span>
            )}
          </div>

          <div className="mt-auto flex items-center justify-between gap-2 border-t border-border/40 pt-4">
            {canOperate && (
              <Button
                type="button"
                size="sm"
                variant={camera.is_running ? "destructive" : "default"}
                onClick={onToggle}
                disabled={pending || deletePending}
                className={`flex-1 gap-1.5 rounded-xl text-xs font-bold ${
                  !camera.is_running
                    ? "bg-primary/12 text-primary hover:bg-primary hover:text-primary-foreground"
                    : ""
                }`}
              >
                {pending ? (
                  <Loader2 className="size-3 animate-spin" />
                ) : camera.is_running ? (
                  <Square size={12} fill="currentColor" />
                ) : (
                  <Play size={12} fill="currentColor" />
                )}
                {camera.is_running ? "إيقاف" : "تشغيل"}
              </Button>
            )}

            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label={`مشاهدة ${camera.name}`}
              onClick={onWatch}
              disabled={deletePending}
              className="shrink-0 rounded-xl text-muted-foreground hover:bg-primary/10 hover:text-primary"
            >
              <MonitorPlay size={16} />
            </Button>

            {canOperate && (
              <>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`تعديل ${camera.name}`}
                  onClick={onEdit}
                  disabled={deletePending}
                  className="shrink-0 rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <Pencil size={16} />
                </Button>

                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`حذف ${camera.name}`}
                  onClick={onDelete}
                  disabled={deletePending}
                  className="shrink-0 rounded-xl text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                >
                  {deletePending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Trash2 size={16} />
                  )}
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>
    </div>
  )
}
