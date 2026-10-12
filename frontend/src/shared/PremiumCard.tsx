import type { HTMLAttributes } from "react"
import { cn } from "@/lib/utils"

type Props = HTMLAttributes<HTMLDivElement> & { featured?: boolean }

export function PremiumCard({ className, featured = false, ...props }: Props) {
  return (
    <div
      data-slot="premium-card"
      className={cn("card-premium rounded-2xl border border-border/70 bg-card text-card-foreground", featured && "card-featured", className)}
      {...props}
    />
  )
}
