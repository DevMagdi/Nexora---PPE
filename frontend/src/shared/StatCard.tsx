import type { ReactNode } from "react"
import { useCountUp } from "@/hooks/useCountUp"
import type { ToneKey } from "@/types/app"
import { cn } from "@/lib/utils"
import { LiveDot } from "@/shared/LiveDot"
import { PremiumCard } from "@/shared/PremiumCard"

const TONE_CLASSES: Record<ToneKey, { icon: string; value: string }> = {
  primary: { icon: "bg-primary-light text-primary", value: "text-primary" },
  info: { icon: "bg-info-light text-info-foreground", value: "text-info-foreground" },
  warning: { icon: "bg-warning-light text-warning-foreground", value: "text-warning-foreground" },
  destructive: { icon: "bg-destructive-light text-destructive-foreground", value: "text-destructive-foreground" },
  success: { icon: "bg-success-light text-success-foreground", value: "text-success-foreground" },
}

type Props = {
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

export function StatCard({ label, value, icon, tone = "primary", unit, plus, hint, live, featured, loading = false }: Props) {
  const animated = useCountUp(value)
  const style = TONE_CLASSES[tone]
  return (
    <PremiumCard featured={featured} className="group relative flex h-full min-h-40 flex-col justify-between overflow-hidden p-5 sm:min-h-44 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className={cn("flex size-11 items-center justify-center rounded-xl", style.icon)}>{icon}</div>
        {live !== undefined && <LiveDot tone={tone === "destructive" ? "destructive" : "success"} active={live} />}
      </div>
      <div className="mt-5">
        <div className={cn("text-3xl font-bold leading-none tabular-nums sm:text-4xl", featured ? "text-gradient" : "text-foreground")}>
          {loading ? <span className="skeleton-shimmer inline-block h-8 w-16 rounded-lg align-middle" aria-label="جارٍ التحميل" /> : animated === undefined ? "—" : <>{animated}{plus && "+"}{unit && <span className="ms-0.5 text-xl">{unit}</span>}</>}
        </div>
        <div className="mt-2.5 text-sm font-semibold text-foreground/85">{label}</div>
        {hint && <div className="mt-1.5 line-clamp-2 text-xs leading-5 text-muted-foreground">{hint}</div>}
      </div>
    </PremiumCard>
  )
}
