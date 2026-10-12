import { useCountUp } from "@/hooks/useCountUp"
import { LiveDot } from "@/shared/LiveDot"
import { PremiumCard } from "@/shared/PremiumCard"

export function ComplianceRing({ value, live, hint }: { value: number | undefined; live: boolean; hint: string }) {
  const animated = useCountUp(value)
  const radius = 48
  const circumference = 2 * Math.PI * radius
  const percent = value ?? 0
  const level = value === undefined ? "none" : percent >= 90 ? "good" : percent >= 70 ? "warn" : "bad"
  const ringColor = { none: "text-muted-foreground/45", good: "text-success", warn: "text-warning", bad: "text-destructive" }[level]
  const textColor = { none: "text-muted-foreground", good: "text-success-foreground", warn: "text-warning-foreground", bad: "text-destructive-foreground" }[level]
  const status = { none: "لا يوجد بث نشط", good: "التزام ممتاز", warn: "يحتاج متابعة", bad: "مستوى خطر" }[level]

  return (
    <PremiumCard featured className="flex h-full min-h-64 flex-col items-center justify-center gap-4 p-5 text-center sm:flex-row sm:gap-6 sm:text-start lg:flex-col lg:text-center xl:flex-row xl:text-start">
      <div className="relative size-40 shrink-0 sm:size-44">
        <svg viewBox="0 0 128 128" className="size-full -rotate-90" aria-hidden="true">
          <circle cx="64" cy="64" r={radius} fill="none" strokeWidth="9" className="stroke-muted" />
          <circle
            cx="64"
            cy="64"
            r={radius}
            fill="none"
            strokeWidth="9"
            strokeLinecap="round"
            stroke="currentColor"
            className={`${ringColor} transition-[stroke-dashoffset] duration-700`}
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - percent / 100)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center" dir="ltr">
          <span className="text-4xl font-bold tabular-nums sm:text-5xl">{animated === undefined ? "—" : `${animated}%`}</span>
        </div>
      </div>
      <div className="min-w-0">
        <div className="flex items-center justify-center gap-2 sm:justify-start lg:justify-center xl:justify-start">
          <h3 className="text-sm font-semibold text-muted-foreground">نسبة الالتزام بالخوذة</h3>
          <LiveDot tone="success" active={live} />
        </div>
        <p className={`mt-1.5 text-lg font-bold ${textColor}`}>{status}</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{hint}</p>
      </div>
    </PremiumCard>
  )
}
