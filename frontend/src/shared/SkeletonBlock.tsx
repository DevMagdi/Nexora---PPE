import { cn } from "@/lib/utils"

export function SkeletonBlock({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("skeleton-shimmer rounded-lg", className)} {...props} />
}
