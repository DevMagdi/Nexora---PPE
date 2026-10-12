import type { ReactNode } from "react"
import { useCountUp } from "@/hooks/useCountUp"
import { PremiumCard } from "@/shared/PremiumCard"

export function SideMetric({ icon, value, label }: { icon: ReactNode; value: number | undefined; label: string }) {
  const animated = useCountUp(value)
  return (
    <PremiumCard className="flex min-h-24 flex-col items-center justify-center gap-1.5 p-3 text-center">
      {icon}
      <span className="text-lg font-bold tabular-nums">{animated ?? "—"}</span>
      <span className="text-[11px] font-semibold text-muted-foreground">{label}</span>
    </PremiumCard>
  )
}
