import type { ReactNode } from "react"
import { useCountUp } from "@/hooks/useUiHooks"
import { TONE_CLASSES } from "@/lib/formatters"
import Card from "@/shared/Card"
import LiveDot from "@/shared/LiveDot"
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
}: StatCardProps) {
  const animated = useCountUp(value)
  const t = TONE_CLASSES[tone]
  return (
    <Card featured={featured} className="group relative h-full overflow-hidden p-7">
      <div className="mb-6 flex items-start justify-between">
        <div className={`flex size-12 items-center justify-center rounded-xl ${t.chip} ${t.text}`}>
          {icon}
        </div>
        {live !== undefined && (
          <LiveDot tone={tone === "destructive" ? "destructive" : "success"} active={live} />
        )}
      </div>
      <div
        className={`text-[2.5rem] font-bold leading-none tabular-nums ${
          featured ? "text-gradient" : "text-foreground"
        }`}
      >
        {animated === undefined ? (
          "—"
        ) : (
          <>
            {animated}
            {plus && "+"}
            {unit && <span className="ms-0.5 text-2xl">{unit}</span>}
          </>
        )}
      </div>
      <div className="mt-3 text-sm font-medium text-muted-foreground">{label}</div>
      {hint && <div className="mt-3 truncate text-[11px] font-medium text-muted-foreground">{hint}</div>}
    </Card>
  )
}
