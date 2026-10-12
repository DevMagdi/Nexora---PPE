import type { HTMLAttributes } from "react"
import { cn } from "@/lib/utils"

type Props = HTMLAttributes<HTMLSpanElement> & {
  tone?: "success" | "warning" | "destructive"
  active?: boolean
}

export function LiveDot({ tone = "success", active = true, className, ...props }: Props) {
  const color = {
    success: "bg-success",
    warning: "bg-warning",
    destructive: "bg-destructive",
  }[tone]
  return (
    <span className={cn("relative inline-flex size-2 shrink-0", className)} aria-hidden="true" {...props}>
      {active && <span className={cn("absolute inset-0 animate-ping rounded-full opacity-45", color)} />}
      <span className={cn("relative size-2 rounded-full", active ? color : "bg-muted-foreground/40")} />
    </span>
  )
}
