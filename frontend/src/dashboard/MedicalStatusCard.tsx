import { Stethoscope } from "lucide-react"
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
  const badgeClass = {
    none: "bg-muted text-muted-foreground",
    good: "bg-success-light text-success-foreground",
    bad: "bg-destructive-light text-destructive-foreground",
  }[level]
  const status = {
    none: "بانتظار البث الحي",
    good: "الكادر الطبي ملتزم",
    bad: "مخالفات وقائية مرصودة",
  }[level]

  return (
    <Card featured className="flex h-full flex-col items-center justify-between gap-5 p-6 text-center sm:flex-row sm:text-start lg:flex-col lg:text-center xl:flex-row xl:text-start">
      <div className="flex size-32 shrink-0 flex-col items-center justify-center rounded-2xl border border-border/60 bg-card/80 shadow-inner">
        <div className={`text-5xl font-bold tabular-nums ${textClass}`}>
          {animated === undefined ? "—" : animated}
        </div>
        <span className="mt-1 text-[10px] font-bold text-muted-foreground">حالة بالكادر</span>
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-center justify-center gap-2 sm:justify-start lg:justify-center xl:justify-start">
          <Stethoscope className="size-4 text-primary" />
          <h3 className="text-xs font-bold text-muted-foreground">الرصد الطبي اللحظي</h3>
          <LiveDot tone={level === "bad" ? "destructive" : "success"} active={live} />
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
