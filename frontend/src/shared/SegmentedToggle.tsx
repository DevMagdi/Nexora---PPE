import { cn } from "@/lib/utils"

type Props = {
  checked: boolean
  onChange: (value: boolean) => void
  labelOn: string
  labelOff: string
  className?: string
  ariaLabel?: string
}

export function SegmentedToggle({ checked, onChange, labelOn, labelOff, className, ariaLabel }: Props) {
  const buttonClass = "relative z-10 min-h-11 rounded-lg px-3 text-xs transition-colors sm:px-3.5"
  return (
    <div role="group" aria-label={ariaLabel} className={cn("relative inline-grid shrink-0 grid-cols-2 rounded-xl border border-border/80 bg-muted/70 p-1 text-xs font-semibold", className)}>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute bottom-1 start-1 top-1 w-[calc(50%-4px)] rounded-lg border border-border/60 bg-card shadow-sm transition-transform duration-200 ease-out"
        style={{ transform: checked ? "translateX(-100%)" : "translateX(0)" }}
      />
      <button type="button" aria-pressed={!checked} onClick={() => onChange(false)} className={cn(buttonClass, !checked ? "font-bold text-foreground" : "text-muted-foreground")}>
        {labelOff}
      </button>
      <button type="button" aria-pressed={checked} onClick={() => onChange(true)} className={cn(buttonClass, checked ? "font-bold text-foreground" : "text-muted-foreground")}>
        {labelOn}
      </button>
    </div>
  )
}
