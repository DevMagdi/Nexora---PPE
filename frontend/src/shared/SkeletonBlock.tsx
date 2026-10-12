interface SkeletonBlockProps {
  className?: string
}

export default function SkeletonBlock({ className = "h-4 w-full rounded-lg" }: SkeletonBlockProps) {
  return <div aria-hidden="true" className={`skeleton-shimmer ${className}`} />
}
