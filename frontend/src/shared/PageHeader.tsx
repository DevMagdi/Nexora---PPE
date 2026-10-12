import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

type Props = {
  title: string
  description?: string
  action?: ReactNode
  eyebrow?: string
  className?: string
}

export function PageHeader({ title, description, action, eyebrow, className }: Props) {
  return (
    <div className={cn("flex flex-col justify-between gap-4 sm:flex-row sm:items-end", className)}>
      <div className="min-w-0">
        {eyebrow && <p className="mb-2 text-xs font-semibold tracking-wide text-primary">{eyebrow}</p>}
        <h2 className="text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">{title}</h2>
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
