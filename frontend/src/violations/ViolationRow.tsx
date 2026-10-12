import { Eye, Image as ImageIcon, Loader2, ShieldCheck } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { resolveFrameUrl } from "@/lib/api"
import { formatDate, formatTime, isCoreType, violationLabel } from "@/lib/formatters"
import type { Violation } from "@/types"

interface ViolationRowProps {
  violation: Violation
  ppeLabels: Map<string, string>
  cameraName: string
  canOperate: boolean
  resolvePending: boolean
  onOpenFrame: (url?: string | null) => void
  onResolve: (v: Violation) => void
}

export default function ViolationRow({
  violation: v,
  ppeLabels,
  cameraName,
  canOperate,
  resolvePending,
  onOpenFrame,
  onResolve,
}: ViolationRowProps) {
  const conf = Math.min(100, Math.max(0, Math.round(v.confidence * 100)))
  const barColor = conf >= 85 ? "bg-success" : conf >= 60 ? "bg-warning" : "bg-destructive"
  const thumb = resolveFrameUrl(v.frame_url)

  return (
    <tr className="group transition-colors hover:bg-muted/60">
      <td className="p-4">
        <button
          type="button"
          onClick={() => onOpenFrame(v.frame_url)}
          disabled={!thumb}
          aria-label={thumb ? "عرض اللقطة" : "لا توجد لقطة"}
          className="block overflow-hidden rounded-xl border border-border/50 transition-all hover:border-primary/40 hover:shadow-md hover:shadow-primary/10 disabled:cursor-default disabled:hover:border-border/50 disabled:hover:shadow-none"
        >
          {thumb ? (
            <img
              src={thumb}
              loading="lazy"
              alt=""
              className="h-10 w-14 object-cover transition-transform duration-300 group-hover:scale-110"
            />
          ) : (
            <div className="flex h-10 w-14 items-center justify-center bg-secondary text-muted-foreground">
              <ImageIcon size={16} />
            </div>
          )}
        </button>
      </td>
      <td className="p-4">
        <div className="text-xs font-semibold text-foreground">{formatDate(v.timestamp)}</div>
        <div className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">
          {formatTime(v.timestamp)}
        </div>
      </td>
      <td className="p-4">
        <Badge
          variant={isCoreType(v.violation_type) ? "destructive" : "secondary"}
          className="rounded-md text-[11px] font-bold"
        >
          {violationLabel(v.violation_type, ppeLabels)}
        </Badge>
      </td>
      <td className="p-4 text-xs text-muted-foreground">{cameraName}</td>
      <td className="p-4">
        <div className="flex items-center gap-2.5">
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all duration-500 ${barColor}`}
              style={{ width: `${conf}%` }}
            />
          </div>
          <span className="w-9 text-xs font-bold tabular-nums text-foreground">{conf}%</span>
        </div>
      </td>

      <td className="p-4">
        {v.is_resolved ? (
          <Badge variant="secondary" className="rounded-md text-[11px] font-bold">
            تمت المعالجة
          </Badge>
        ) : (
          <Badge
            variant="outline"
            className="rounded-md border-destructive/30 text-[11px] font-bold text-destructive"
          >
            جديدة
          </Badge>
        )}
      </td>

      <td className="p-4 text-end">
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={!thumb}
            onClick={() => onOpenFrame(v.frame_url)}
            className="h-8 gap-1.5 rounded-lg text-xs text-muted-foreground hover:bg-primary-light hover:text-primary"
          >
            <Eye size={14} /> عرض
          </Button>

          {canOperate && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={v.is_resolved || resolvePending}
              onClick={() => onResolve(v)}
              className="h-8 gap-1.5 rounded-lg text-xs text-muted-foreground hover:bg-success/10 hover:text-success-foreground disabled:opacity-50"
            >
              {resolvePending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <ShieldCheck size={14} />
              )}
              {v.is_resolved ? "مُعالجة" : "تعليم كمعالجة"}
            </Button>
          )}
        </div>
      </td>
    </tr>
  )
}
