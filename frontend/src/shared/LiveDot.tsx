interface LiveDotProps {
  tone?: "success" | "warning" | "destructive"
  active?: boolean
}

export default function LiveDot({ tone = "success", active = true }: LiveDotProps) {
  const bg = {
    success: "bg-success",
    warning: "bg-warning",
    destructive: "bg-destructive",
  }[tone]

  return (
    <span className="relative inline-flex size-2.5 shrink-0" aria-hidden="true">
      {active && (
        <span
          className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${bg}`}
        />
      )}
      <span
        className={`relative inline-flex size-2.5 rounded-full ${
          active ? bg : "bg-muted-foreground/40"
        }`}
      />
    </span>
  )
}
