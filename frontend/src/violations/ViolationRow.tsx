import { Eye, Image as ImageIcon, ShieldCheck, Loader2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { resolveFrameUrl } from "@/lib/api"
import { formatDate, formatRelative, formatTime, isCoreType, violationLabel } from "@/lib/domain"
import type { Violation } from "@/types"
import { PremiumCard } from "@/shared/PremiumCard"

export interface ViolationItemProps {
  violation: Violation
  ppeLabels: Map<string, string>
  cameraName: (id: number) => string
  now: number
  canOperate: boolean
  pending: boolean
  onResolve: (violation: Violation) => void
  onOpenFrame: (url?: string | null) => void
}

function buildViewModel(violation: Violation, ppeLabels: Map<string, string>) {
  const thumb = resolveFrameUrl(violation.frame_url)
  const confidence = Math.max(0, Math.min(100, Math.round((Number(violation.confidence) || 0) * 100)))
  const barColor = confidence >= 85 ? "bg-success" : confidence >= 60 ? "bg-warning" : "bg-destructive"
  return { thumb, confidence, barColor, label: violationLabel(violation.violation_type, ppeLabels) }
}

export function ViolationTableRow({ violation, ppeLabels, cameraName, canOperate, pending, onResolve, onOpenFrame }: ViolationItemProps) {
  const { thumb, confidence, barColor, label } = buildViewModel(violation, ppeLabels)
  return (
    <tr className="group transition-colors hover:bg-muted/40">
      <td className="p-3.5"><FrameButton thumb={thumb} label={label} onClick={() => onOpenFrame(violation.frame_url)} /></td>
      <td className="p-3.5">
        <div className="text-xs font-semibold text-foreground">{formatDate(violation.timestamp)}</div>
        <div className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">{formatTime(violation.timestamp)}</div>
      </td>
      <td className="p-3.5"><ViolationTypeBadge violation={violation} label={label} /></td>
      <td className="max-w-40 truncate p-3.5 text-xs text-muted-foreground">{cameraName(violation.camera_id)}</td>
      <td className="p-3.5"><Confidence confidence={confidence} barColor={barColor} /></td>
      <td className="p-3.5"><ViolationStatus resolved={violation.is_resolved} /></td>
      <td className="p-3.5 text-end">
        <div className="flex justify-end gap-1.5">
          <Button type="button" variant="ghost" size="sm" disabled={!thumb} onClick={() => onOpenFrame(violation.frame_url)} className="min-h-10 gap-1.5 rounded-lg text-xs text-muted-foreground hover:bg-primary-light hover:text-primary"><Eye className="size-3.5" /> عرض</Button>
          {canOperate && <ResolveButton violation={violation} pending={pending} onResolve={onResolve} />}
        </div>
      </td>
    </tr>
  )
}

export function ViolationCard({ violation, ppeLabels, cameraName, now, canOperate, pending, onResolve, onOpenFrame }: ViolationItemProps) {
  const { thumb, confidence, barColor, label } = buildViewModel(violation, ppeLabels)
  return (
    <PremiumCard className="p-3.5 sm:p-4">
      <div className="flex items-start gap-3">
        <FrameButton thumb={thumb} label={label} onClick={() => onOpenFrame(violation.frame_url)} className="size-16" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <ViolationTypeBadge violation={violation} label={label} />
            <ViolationStatus resolved={violation.is_resolved} />
          </div>
          <p className="mt-2 truncate text-sm font-semibold">{cameraName(violation.camera_id)}</p>
          <p className="mt-1 text-xs text-muted-foreground">{formatRelative(violation.timestamp, now)} · الثقة <strong className="tabular-nums text-foreground">{confidence}%</strong></p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-border/60 pt-3">
        <div className="min-w-0">
          <Confidence confidence={confidence} barColor={barColor} />
          <span className="mt-1 block text-[11px] text-muted-foreground">{formatDate(violation.timestamp)} · {formatTime(violation.timestamp)}</span>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button type="button" variant="outline" size="icon" aria-label={thumb ? "عرض الدليل المرئي" : "لا توجد لقطة"} disabled={!thumb} onClick={() => onOpenFrame(violation.frame_url)} className="tap-target rounded-xl"><Eye className="size-4" /></Button>
          {canOperate && <ResolveButton violation={violation} pending={pending} onResolve={onResolve} />}
        </div>
      </div>
    </PremiumCard>
  )
}

function FrameButton({ thumb, label, onClick, className = "" }: { thumb: string | null; label: string; onClick: () => void; className?: string }) {
  return (
    <button type="button" onClick={onClick} disabled={!thumb} aria-label={thumb ? `عرض لقطة ${label}` : "لا توجد لقطة متاحة"} className={`block size-12 shrink-0 overflow-hidden rounded-xl border border-border/70 bg-muted transition-colors hover:border-primary/40 disabled:cursor-default ${className}`}>
      {thumb ? <img src={thumb} loading="lazy" alt="" className="size-full object-cover" /> : <span className="flex size-full items-center justify-center text-muted-foreground"><ImageIcon className="size-4" /></span>}
    </button>
  )
}

function ViolationTypeBadge({ violation, label }: { violation: Violation; label: string }) {
  return <Badge variant={isCoreType(violation.violation_type) ? "destructive" : "secondary"} className="rounded-md text-[11px] font-bold">{label}</Badge>
}

function ViolationStatus({ resolved }: { resolved: boolean }) {
  return resolved
    ? <Badge variant="secondary" className="rounded-md text-[11px] font-semibold">تمت المعالجة</Badge>
    : <Badge variant="outline" className="rounded-md border-destructive/30 bg-destructive-light/50 text-[11px] font-semibold text-destructive-foreground">مفتوحة</Badge>
}

function Confidence({ confidence, barColor }: { confidence: number; barColor: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full transition-[width] duration-500 ${barColor}`} style={{ width: `${confidence}%` }} /></div>
      <span className="w-9 text-xs font-bold tabular-nums text-foreground">{confidence}%</span>
    </div>
  )
}

function ResolveButton({ violation, pending, onResolve }: { violation: Violation; pending: boolean; onResolve: (violation: Violation) => void }) {
  return (
    <Button type="button" variant={violation.is_resolved ? "secondary" : "outline"} size="sm" disabled={violation.is_resolved || pending} onClick={() => onResolve(violation)} className="min-h-11 gap-1.5 rounded-lg px-3 text-xs">
      {pending ? <Loader2 className="size-3.5 animate-spin" /> : <ShieldCheck className="size-3.5" />}
      {violation.is_resolved ? "مُعالجة" : "تعليم كمعالجة"}
    </Button>
  )
}
