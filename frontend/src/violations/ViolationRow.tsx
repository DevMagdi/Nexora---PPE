import { Eye, Image as ImageIcon, Loader2, ShieldCheck } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { resolveFrameUrl } from "@/lib/api"
import {
  formatDate,
  formatRelative,
  formatTime,
  isCoreType,
  violationLabel,
} from "@/lib/formatters"
import type { Violation } from "@/types"

export interface ViolationRowProps {
  violation: Violation
  ppeLabels: Map<string, string>
  cameraName: string
  now: number
  canOperate: boolean
  resolvePending: boolean
  onOpenFrame: (url?: string | null) => void
  onResolve: (v: Violation) => void
}

export default function ViolationRow({
  violation: v,
  ppeLabels,
  cameraName,
  now,
  canOperate,
  resolvePending,
  onOpenFrame,
  onResolve,
}: ViolationRowProps) {
  const conf = Math.min(100, Math.max(0, Math.round(v.confidence * 100)))
  const barColor = conf >= 85 ? "bg-success" : conf >= 60 ? "bg-warning" : "bg-destructive"
  const thumb = resolveFrameUrl(v.frame_url)

  return (
    <tr className="group transition-colors hover:bg-muted/50">
      <td className="p-4">
        <button
          type="button"
          onClick={() => onOpenFrame(v.frame_url)}
          disabled={!thumb}
          aria-label={thumb ? "عرض اللقطة" : "لا توجد لقطة"}
          className="block overflow-hidden rounded-xl border border-border/60 transition-all hover:border-primary/40 hover:shadow-md hover:shadow-primary/10 disabled:cursor-default disabled:hover:border-border/60 disabled:hover:shadow-none"
        >
          {thumb ? (
            <img
              src={thumb}
              loading="lazy"
              alt=""
              className="h-11 w-16 object-cover transition-transform duration-300 group-hover:scale-110"
            />
          ) : (
            <div className="flex h-11 w-16 items-center justify-center bg-secondary text-muted-foreground">
              <ImageIcon size={16} />
            </div>
          )}
        </button>
      </td>
      <td className="p-4">
        <div className="text-xs font-bold text-foreground">{formatRelative(v.timestamp, now)}</div>
        <div className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">
          {formatDate(v.timestamp)} · {formatTime(v.timestamp)}
        </div>
      </td>
      <td className="p-4">
        <Badge
          variant={isCoreType(v.violation_type) ? "destructive" : "secondary"}
          className="rounded-md px-2.5 py-0.5 text-[11px] font-bold"
        >
          {violationLabel(v.violation_type, ppeLabels)}
        </Badge>
      </td>
      <td className="p-4 text-xs font-medium text-foreground/85">{cameraName}</td>
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
          <span className="inline-flex items-center gap-1 rounded-md bg-success-light px-2.5 py-1 text-[11px] font-bold text-success-foreground">
            <ShieldCheck className="size-3" /> تمت المعالجة
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-destructive-light px-2.5 py-1 text-[11px] font-bold text-destructive-foreground">
            <span className="size-1.5 rounded-full bg-destructive" />
            جديدة
          </span>
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
            className="h-9 gap-1.5 rounded-xl text-xs text-muted-foreground hover:bg-primary-light hover:text-primary"
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
              className="h-9 gap-1.5 rounded-xl text-xs font-semibold text-muted-foreground hover:bg-success-light hover:text-success-foreground disabled:opacity-50"
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

export function ViolationMobileCard({
  violation: v,
  ppeLabels,
  cameraName,
  now,
  canOperate,
  resolvePending,
  onOpenFrame,
  onResolve,
}: ViolationRowProps) {
  const conf = Math.min(100, Math.max(0, Math.round(v.confidence * 100)))
  const thumb = resolveFrameUrl(v.frame_url)

  return (
    <div className="card-premium space-y-3.5 border border-border/70 p-4">
      <div className="flex items-start gap-3.5">
        <button
          type="button"
          onClick={() => onOpenFrame(v.frame_url)}
          disabled={!thumb}
          aria-label={thumb ? "عرض اللقطة" : "لا توجد لقطة"}
          className="shrink-0 overflow-hidden rounded-xl border border-border/60"
        >
          {thumb ? (
            <img src={thumb} loading="lazy" alt="" className="size-16 object-cover" />
          ) : (
            <div className="flex size-16 items-center justify-center bg-secondary text-muted-foreground">
              <ImageIcon size={18} />
            </div>
          )}
        </button>

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Badge
              variant={isCoreType(v.violation_type) ? "destructive" : "secondary"}
              className="rounded-md px-2 py-0.5 text-xs font-bold"
            >
              {violationLabel(v.violation_type, ppeLabels)}
            </Badge>
            {v.is_resolved ? (
              <span className="rounded-md bg-success-light px-2 py-0.5 text-[11px] font-bold text-success-foreground">
                تمت المعالجة
              </span>
            ) : (
              <span className="rounded-md bg-destructive-light px-2 py-0.5 text-[11px] font-bold text-destructive-foreground">
                جديدة
              </span>
            )}
          </div>

          <div className="truncate text-xs font-bold text-foreground">{cameraName}</div>
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>{formatRelative(v.timestamp, now)}</span>
            <span className="tabular-nums font-semibold">ثقة الكشف: {conf}%</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 border-t border-border/50 pt-3">
        <Button
          type="button"
          variant="outline"
          disabled={!thumb}
          onClick={() => onOpenFrame(v.frame_url)}
          className="min-h-11 flex-1 gap-1.5 rounded-xl text-xs font-semibold"
        >
          <Eye size={15} /> عرض اللقطة
        </Button>

        {canOperate && (
          <Button
            type="button"
            variant={v.is_resolved ? "secondary" : "default"}
            disabled={v.is_resolved || resolvePending}
            onClick={() => onResolve(v)}
            className="min-h-11 flex-1 gap-1.5 rounded-xl text-xs font-bold"
          >
            {resolvePending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ShieldCheck size={15} />
            )}
            {v.is_resolved ? "تمت المعالجة" : "تعليم كمعالجة"}
          </Button>
        )}
      </div>
    </div>
  )
}
