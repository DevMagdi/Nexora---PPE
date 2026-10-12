import type { ReactNode } from "react"
import { Sparkles } from "lucide-react"

interface EmptyStateProps {
  title: string
  desc?: string
  action?: ReactNode
  icon?: ReactNode
  compact?: boolean
}

export default function EmptyState({
  title,
  desc,
  action,
  icon,
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center px-6 text-center ${
        compact
          ? "py-10"
          : "rounded-2xl border border-dashed border-border bg-card/80 py-16 shadow-xs"
      }`}
    >
      <div className="relative mb-5 flex size-20 items-center justify-center" aria-hidden="true">
        <span className="absolute inset-0 animate-soft-pulse rounded-full bg-primary/15" />
        <span className="absolute inset-0 rounded-full bg-primary-light" />
        <span className="absolute inset-2.5 rounded-full bg-card ring-1 ring-primary/20" />
        <span className="absolute -end-1 top-1 size-3 animate-soft-float rounded-full bg-primary/30" />
        <span className="absolute -start-1 bottom-2 size-2 animate-soft-float rounded-full bg-primary/40 [animation-delay:1.2s]" />
        <span className="relative">{icon ?? <Sparkles className="size-6 text-primary" />}</span>
      </div>
      <h3 className="text-base font-bold text-foreground">{title}</h3>
      {desc && <p className="mt-2 max-w-sm text-xs leading-relaxed text-muted-foreground">{desc}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
