import type { ReactNode } from "react"
import { Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

type Props = {
  title: string
  desc?: string
  action?: ReactNode
  icon?: ReactNode
  compact?: boolean
  className?: string
}

export function EmptyState({ title, desc, action, icon, compact = false, className }: Props) {
  return (
    <div className={cn("flex flex-col items-center justify-center text-center", compact ? "py-8" : "rounded-2xl border border-dashed border-border bg-card px-5 py-14", className)}>
      <div className={cn("relative mb-4 flex items-center justify-center", compact ? "size-14" : "size-16")} aria-hidden="true">
        <span className="absolute inset-0 rounded-full bg-primary-light" />
        <span className="absolute inset-2 rounded-full bg-card ring-1 ring-primary/15" />
        <span className="relative">{icon ?? <Sparkles className="size-5 text-primary" />}</span>
      </div>
      <h3 className="text-sm font-semibold text-foreground sm:text-base">{title}</h3>
      {desc && <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-muted-foreground sm:text-sm">{desc}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
