import { useCountUp } from "@/hooks/useUiHooks"
import Card from "@/shared/Card"
import LiveDot from "@/shared/LiveDot"

interface ComplianceRingProps {
  value: number | undefined
  live: boolean
  hint: string
}

export default function ComplianceRing({ value, live, hint }: ComplianceRingProps) {
  const animated = useCountUp(value)
  const R = 54
  const C = 2 * Math.PI * R
  const v = value ?? 0
  const level = value === undefined ? "none" : v >= 90 ? "good" : v >= 70 ? "warn" : "bad"
  const ringClass = {
    none: "text-muted-foreground",
    good: "text-success",
    warn: "text-warning",
    bad: "text-destructive",
  }[level]
  const textClass = {
    none: "text-muted-foreground",
    good: "text-success-foreground",
    warn: "text-warning-foreground",
    bad: "text-destructive-foreground",
  }[level]
  const status = {
    none: "لا يوجد بث",
    good: "التزام ممتاز",
    warn: "يحتاج متابعة",
    bad: "مستوى خطر",
  }[level]

  return (
    <Card className="flex h-full flex-col items-center justify-center gap-5 p-6 text-center sm:flex-row sm:text-start lg:flex-col lg:text-center xl:flex-row xl:text-start">
      <div className="relative size-44 shrink-0">
        <svg viewBox="0 0 128 128" className="size-full -rotate-90" aria-hidden="true">
          <circle cx="64" cy="64" r={R} fill="none" strokeWidth="10" className="stroke-muted" />
          <circle
            cx="64"
            cy="64"
            r={R}
            fill="none"
            strokeWidth="10"
            strokeLinecap="round"
            stroke="currentColor"
            className={`${ringClass} transition-[stroke-dashoffset] duration-700`}
            strokeDasharray={C}
            strokeDashoffset={C * (1 - v / 100)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center" dir="ltr">
          <span className="text-5xl font-bold tabular-nums">
            {animated === undefined ? "—" : `${animated}%`}
          </span>
        </div>
      </div>
      <div className="min-w-0">
        <div className="flex items-center justify-center gap-2 sm:justify-start lg:justify-center xl:justify-start">
          <h3 className="text-sm font-semibold text-muted-foreground">نسبة الالتزام بالخوذة</h3>
          <LiveDot tone="success" active={live} />
        </div>
        <p className={`mt-1.5 text-lg font-bold ${textClass}`}>{status}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </div>
    </Card>
  )
}
