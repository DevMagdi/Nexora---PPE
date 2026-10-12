import { ShieldCheck } from "lucide-react"
import { useCountUp } from "@/hooks/useCountUp"
import { LiveDot } from "@/shared/LiveDot"
import { PremiumCard } from "@/shared/PremiumCard"

export function MedicalStatusCard({ count, live, hint }: { count: number | undefined; live: boolean; hint: string }) {
  const animated = useCountUp(count)
  const level = count === undefined ? "none" : count === 0 ? "good" : "bad"
  const textColor = { none: "text-muted-foreground", good: "text-success-foreground", bad: "text-destructive-foreground" }[level]
  const status = { none: "لا يوجد بث نشط", good: "الكادر ملتزم", bad: "مخالفات ظاهرة" }[level]
  return (
    <PremiumCard featured className="flex h-full min-h-64 flex-col items-center justify-center gap-4 p-6 text-center sm:flex-row sm:gap-6 sm:text-start lg:flex-col lg:text-center xl:flex-row xl:text-start">
      <div className={`flex size-36 shrink-0 items-center justify-center rounded-full bg-primary-light ${textColor}`}>
        <div className="flex size-28 flex-col items-center justify-center rounded-full border border-border/70 bg-card shadow-card">
          <ShieldCheck className="mb-1 size-5 text-primary" />
          <span className="text-4xl font-bold tabular-nums">{animated === undefined ? "—" : animated}</span>
        </div>
      </div>
      <div className="min-w-0">
        <div className="flex items-center justify-center gap-2 sm:justify-start lg:justify-center xl:justify-start">
          <h3 className="text-sm font-semibold text-muted-foreground">مخالفات معدات طبية ظاهرة</h3>
          <LiveDot tone={level === "bad" ? "destructive" : "success"} active={live} />
        </div>
        <p className={`mt-1.5 text-lg font-bold ${textColor}`}>{status}</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{hint}</p>
      </div>
    </PremiumCard>
  )
}
