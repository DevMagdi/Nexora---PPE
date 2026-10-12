import { HardHat } from "lucide-react"
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
  const R = 52
  const C = 2 * Math.PI * R
  const v = value ?? 0
  const level = value === undefined ? "none" : v >= 90 ? "good" : v >= 70 ? "warn" : "bad"
  const ringClass = {
    none: "text-muted-foreground/30",
    good: "text-success",
    warn: "text-warning",
    bad: "text-destructive",
  }[level]
  const badgeClass = {
    none: "bg-muted text-muted-foreground",
    good: "bg-success-light text-success-foreground",
    warn: "bg-warning-light text-warning-foreground",
    bad: "bg-destructive-light text-destructive-foreground",
  }[level]
  const status = {
    none: "بانتظار البث الحي",
    good: "التزام ممتاز",
    warn: "يحتاج متابعة",
    bad: "مستوى خطر مرتفع",
  }[level]

  return (
    <Card featured className="flex h-full flex-col items-center justify-between gap-5 p-6 text-center sm:flex-row sm:text-start lg:flex-col lg:text-center xl:flex-row xl:text-start">
      <div className="relative size-36 shrink-0 sm:size-40">
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
        <div className="absolute inset-0 flex flex-col items-center justify-center" dir="ltr">
          <span className="text-4xl font-bold tabular-nums tracking-tight text-foreground">
            {animated === undefined ? "—" : `${animated}%`}
          </span>
          <span className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            PPE Index
          </span>
        </div>
      </div>

      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-center justify-center gap-2 sm:justify-start lg:justify-center xl:justify-start">
          <HardHat className="size-4 text-primary" />
          <h3 className="text-xs font-bold text-muted-foreground">مؤشر الالتزام بالخوذة</h3>
          <LiveDot tone="success" active={live} />
        </div>
        <div>
          <span className={`inline-flex items-center rounded-lg px-2.5 py-1 text-xs font-bold ${badgeClass}`}>
            {status}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>
      </div>
    </Card>
  )
}
