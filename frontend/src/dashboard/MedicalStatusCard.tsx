import { useCountUp } from "@/hooks/useUiHooks"
import Card from "@/shared/Card"
import LiveDot from "@/shared/LiveDot"

interface MedicalStatusCardProps {
  count: number | undefined
  live: boolean
  hint: string
}

export default function MedicalStatusCard({ count, live, hint }: MedicalStatusCardProps) {
  const animated = useCountUp(count)
  const level = count === undefined ? "none" : count === 0 ? "good" : "bad"
  const textClass = {
    none: "text-muted-foreground",
    good: "text-success-foreground",
    bad: "text-destructive-foreground",
  }[level]
  const status = {
    none: "لا يوجد بث",
    good: "الكادر ملتزم",
    bad: "مخالفات ظاهرة",
  }[level]

  return (
    <Card className="flex h-full flex-col items-center justify-center gap-5 p-6 text-center sm:flex-row sm:text-start lg:flex-col lg:text-center xl:flex-row xl:text-start">
      <div className={`text-6xl font-bold tabular-nums ${textClass}`}>
        {animated === undefined ? "—" : animated}
      </div>
      <div className="min-w-0">
        <div className="flex items-center justify-center gap-2 sm:justify-start lg:justify-center xl:justify-start">
          <h3 className="text-sm font-semibold text-muted-foreground">مخالفات ظاهرة الآن</h3>
          <LiveDot tone={level === "bad" ? "destructive" : "success"} active={live} />
        </div>
        <p className={`mt-1.5 text-lg font-bold ${textClass}`}>{status}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </div>
    </Card>
  )
}
