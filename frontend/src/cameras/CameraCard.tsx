import {
  Camera as CameraIcon,
  HardHat,
  Loader2,
  Lock,
  MonitorPlay,
  Pencil,
  Play,
  Square,
  Stethoscope,
  Trash2,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useInView } from "@/hooks/useUiHooks"
import { getMjpegStreamUrl } from "@/lib/api"
import { cameraProfile, maskUri, PROFILE_LABEL, SOURCE_TYPE_SHORT } from "@/lib/formatters"
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
  const profile = cameraProfile(camera)

  return (
    <div ref={ref} className="h-full">
      <Card className="group flex h-full flex-col overflow-hidden">
        {/* ─── Video / Status Preview Header ─── */}
        <div className="relative h-44 shrink-0 overflow-hidden bg-slate-950">
          {showStream ? (
            <img
              src={getMjpegStreamUrl(camera.id)}
              loading="lazy"
              className="h-full w-full object-cover opacity-85 transition-all duration-700 group-hover:scale-105 group-hover:opacity-100"
              alt={`معاينة ${camera.name}`}
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-b from-slate-900 to-slate-950 text-slate-400">
              {camera.is_running ? (
                <MonitorPlay className="mb-2 size-10 text-emerald-400/50" />
              ) : (
                <CameraIcon className="mb-2 size-10 opacity-30" />
              )}
              <span className="text-xs font-medium opacity-75">
                {camera.is_running ? "تعمل · اضغط للمشاهدة المباشرة" : "البث متوقف حاليًا"}
              </span>
            </div>
          )}

          <div className="absolute end-3 top-3 flex items-center gap-1.5">
            <span className="rounded-lg border border-white/10 bg-black/70 px-2 py-1 text-[11px] font-semibold text-white backdrop-blur-md">
              {SOURCE_TYPE_SHORT[camera.source_type] ?? camera.source_type}
            </span>
            <span className="rounded-lg border border-white/10 bg-black/70 px-2 py-1 text-[11px] tabular-nums text-white backdrop-blur-md">
              #{camera.id}
            </span>
          </div>

          <div
            className={`absolute start-3 top-3 flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold text-white shadow-sm ${
              !camera.is_running
                ? "bg-slate-700/90"
                : alerts > 0
                  ? "bg-red-600/95"
                  : "bg-emerald-700/95"
            }`}
          >
            <span
              className={`size-1.5 rounded-full bg-white ${
                camera.is_running ? "animate-pulse" : "opacity-60"
              }`}
            />
            {!camera.is_running ? "متوقفة" : alerts > 0 ? `${alerts} تنبيه نشط` : "تعمل الآن"}
          </div>
        </div>

        {/* ─── Card Details & Actions ─── */}
        <div className="flex flex-1 flex-col p-5">
          <div className="mb-3.5">
            <div className="flex items-center justify-between gap-2">
              <h3 className="truncate text-base font-bold text-foreground transition-colors group-hover:text-primary">
                {camera.name}
              </h3>
              <span className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-muted px-2 py-0.5 text-[11px] font-bold text-muted-foreground">
                {profile === "medical" ? (
                  <Stethoscope className="size-3 text-info" />
                ) : (
                  <HardHat className="size-3 text-warning" />
                )}
                {PROFILE_LABEL[profile]}
              </span>
            </div>

            <div
              dir="ltr"
              className="mt-2 flex items-center gap-1.5 rounded-lg border border-border/50 bg-muted/40 px-2.5 py-1 text-[11px] font-mono text-muted-foreground"
              title="تم إخفاء بيانات الاعتماد لحماية أمان المصدر"
            >
              <Lock className="size-3 shrink-0 opacity-60" />
              <span className="truncate">{maskUri(camera.source_uri)}</span>
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-1.5">
            {classes.map((k) => (
              <Badge
                key={k}
                variant="outline"
                className="rounded-md border-border/60 bg-muted/40 text-[11px] font-medium text-foreground/80"
              >
                {ppeLabels.get(k) ?? k}
              </Badge>
            ))}
            {classes.length === 0 && (
              <span className="text-[11px] italic text-muted-foreground">لم يتم تحديد فئات</span>
            )}
          </div>

          <div className="mt-auto flex items-center justify-between gap-2 border-t border-border/50 pt-4">
            {canOperate && (
              <Button
                type="button"
                size="sm"
                variant={camera.is_running ? "destructive" : "default"}
                onClick={onToggle}
                disabled={pending || deletePending}
                className={`min-h-10 flex-1 gap-1.5 rounded-xl text-xs font-bold ${
                  !camera.is_running
                    ? "bg-primary-light text-primary hover:bg-primary hover:text-primary-foreground"
                    : ""
                }`}
              >
                {pending ? (
                  <Loader2 className="size-3.5 animate-spin" />
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
              title={`مشاهدة البث المباشر (${camera.name})`}
              onClick={onWatch}
              disabled={deletePending}
              className="size-10 shrink-0 rounded-xl text-muted-foreground hover:bg-primary-light hover:text-primary"
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
                  title={`تعديل إعدادات ${camera.name}`}
                  onClick={onEdit}
                  disabled={deletePending}
                  className="size-10 shrink-0 rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <Pencil size={16} />
                </Button>

                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`حذف ${camera.name}`}
                  title={`حذف ${camera.name}`}
                  onClick={onDelete}
                  disabled={deletePending}
                  className="size-10 shrink-0 rounded-xl text-muted-foreground hover:bg-destructive-light hover:text-destructive"
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
