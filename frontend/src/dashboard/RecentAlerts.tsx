import { ArrowLeft, Image as ImageIcon, ShieldAlert, ShieldCheck } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { Violation } from "@/types"
import { formatRelative, isCoreType, violationLabel } from "@/lib/domain"
import { resolveFrameUrl } from "@/lib/api"
import { EmptyState } from "@/shared/EmptyState"
import { ErrorState } from "@/shared/ErrorState"
import { PremiumCard } from "@/shared/PremiumCard"

interface Props {
  violations: Violation[]
  ppeLabels: Map<string, string>
  cameraName: (id: number) => string
  now: number
  isLoading: boolean
  isError: boolean
  hasData: boolean
  rangeLabel: string
  onRetry: () => void
  onOpenFrame: (url?: string | null) => void
  onShowAll: () => void
}

export function RecentAlerts({ violations, ppeLabels, cameraName, now, isLoading, isError, hasData, rangeLabel, onRetry, onOpenFrame, onShowAll }: Props) {
  return (
    <PremiumCard className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 bg-card/80 p-4 sm:p-5">
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-xl bg-destructive-light text-destructive"><ShieldAlert className="size-4" /></span>
          <div>
            <h3 className="text-sm font-bold">آخر التنبيهات المسجلة</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">خلال {rangeLabel}</p>
          </div>
        </div>
        <button type="button" onClick={onShowAll} className="tap-target flex min-h-11 items-center gap-1 rounded-lg px-2 text-xs font-bold text-primary hover:bg-primary-light">
          عرض السجل الكامل <ArrowLeft className="size-3.5" />
        </button>
      </div>

      <div className="divide-y divide-border/70">
        {isError && !hasData ? (
          <div className="p-4"><ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={onRetry} /></div>
        ) : isLoading && !hasData ? (
          <div className="space-y-3 p-5" aria-label="جارٍ تحميل التنبيهات">{Array.from({ length: 3 }, (_, index) => <div key={index} className="skeleton-shimmer h-16 rounded-xl" />)}</div>
        ) : violations.length === 0 ? (
          <EmptyState compact icon={<ShieldCheck className="size-5 text-success" />} title="كل شيء على ما يرام" desc={`لم يرصد النظام مخالفات خلال ${rangeLabel}.`} />
        ) : (
          violations.slice(0, 6).map((violation) => {
            const thumb = resolveFrameUrl(violation.frame_url)
            return (
              <button key={violation.id} type="button" onClick={() => onOpenFrame(violation.frame_url)} disabled={!thumb} className="group flex min-h-[84px] w-full items-center gap-3 p-3 text-start transition-colors hover:bg-muted/45 disabled:cursor-default sm:gap-4 sm:p-4">
                {thumb ? <img src={thumb} loading="lazy" alt={`لقطة ${violationLabel(violation.violation_type, ppeLabels)}`} className="size-14 shrink-0 rounded-xl border border-border/70 object-cover" /> : <span className="flex size-14 shrink-0 items-center justify-center rounded-xl border border-border/70 bg-muted text-muted-foreground"><ImageIcon className="size-5" /></span>}
                <span className="min-w-0 flex-1 space-y-1.5">
                  <span className="flex flex-wrap items-center gap-2">
                    <Badge variant={isCoreType(violation.violation_type) ? "destructive" : "secondary"} className="rounded-md px-2 py-0.5 text-[11px] font-bold">{violationLabel(violation.violation_type, ppeLabels)}</Badge>
                    <span className="text-[11px] text-muted-foreground">{formatRelative(violation.timestamp, now)}</span>
                  </span>
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
                    <span className="truncate font-semibold text-foreground/85">{cameraName(violation.camera_id)}</span>
                    <span className="text-muted-foreground">الثقة <strong className="tabular-nums text-foreground">{Math.round(violation.confidence * 100)}%</strong></span>
                  </span>
                </span>
                {thumb && <ArrowLeft className="size-4 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-primary" />}
              </button>
            )
          })
        )}
      </div>
    </PremiumCard>
  )
}
