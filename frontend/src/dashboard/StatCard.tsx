import type { ReactNode } from "react"
import { useCountUp } from "@/hooks/useUiHooks"
import { TONE_CLASSES } from "@/lib/formatters"
import Card from "@/shared/Card"
import LiveDot from "@/shared/LiveDot"
import SkeletonBlock from "@/shared/SkeletonBlock"
import type { ToneKey } from "@/types"

export interface StatCardProps {
  label: string
  value: number | undefined
  icon: ReactNode
  tone?: ToneKey
  unit?: string
  plus?: boolean
  hint?: ReactNode
  live?: boolean
  featured?: boolean
  loading?: boolean
}

export default function StatCard({
  label,
  value,
  icon,
  tone = "primary",
  unit,
  plus,
  hint,
  live,
  featured,
  loading = false,
}: StatCardProps) {
  const animated = useCountUp(value)
  const t = TONE_CLASSES[tone]

  return (
    <Card featured={featured} className="group relative flex h-full flex-col justify-between overflow-hidden p-6">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div
          className={`flex size-11 shrink-0 items-center justify-center rounded-xl border ${t.chip} ${t.text} ${t.border}`}
        >
          {icon}
        </div>
        {live !== undefined && (
          <div className="flex items-center gap-1.5 rounded-full bg-muted/70 px-2.5 py-1 text-[10px] font-bold text-muted-foreground">
            <LiveDot tone={tone === "destructive" ? "destructive" : "success"} active={live} />
            <span>{live ? "مباشر" : "غير نشط"}</span>
          </div>
        )}
      </div>

      <div>
        {loading ? (
          <SkeletonBlock className="my-1 h-9 w-24 rounded-xl" />
        ) : (
          <div
            className={`text-3xl font-bold leading-none tabular-nums sm:text-4xl ${
              featured ? "text-gradient" : "text-foreground"
            }`}
          >
            {animated === undefined ? (
              "—"
            ) : (
              <>
                {animated}
                {plus && "+"}
                {unit && <span className="ms-1 text-xl font-semibold">{unit}</span>}
              </>
            )}
          </div>
        )}
        <div className="mt-2.5 text-sm font-bold text-foreground/90">{label}</div>
        {hint && (
          <div className="mt-1.5 truncate text-xs font-medium text-muted-foreground">{hint}</div>
        )}
      </div>
    </Card>
  )
}
