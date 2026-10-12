interface SegToggleProps {
  checked: boolean
  onChange: (v: boolean) => void
  labelOn: string
  labelOff: string
}

export default function SegToggle({ checked, onChange, labelOn, labelOff }: SegToggleProps) {
  const base = "relative z-10 min-h-9 rounded-lg px-3.5 py-1.5 transition-colors cursor-pointer"
  return (
    <div
      role="group"
      className="relative inline-grid grid-cols-2 rounded-xl border border-border/80 bg-muted/60 p-1 text-xs font-semibold"
    >
      <span
        aria-hidden="true"
        className="absolute bottom-1 start-1 top-1 w-[calc(50%-4px)] rounded-lg border border-border/50 bg-card shadow-sm transition-transform duration-200 ease-out"
        style={{ transform: checked ? "translateX(-100%)" : "translateX(0)" }}
      />
      <button
        type="button"
        aria-pressed={!checked}
        onClick={() => onChange(false)}
        className={`${base} ${!checked ? "font-bold text-foreground" : "text-muted-foreground hover:text-foreground"}`}
      >
        {labelOff}
      </button>
      <button
        type="button"
        aria-pressed={checked}
        onClick={() => onChange(true)}
        className={`${base} ${checked ? "font-bold text-foreground" : "text-muted-foreground hover:text-foreground"}`}
      >
        {labelOn}
      </button>
    </div>
  )
}
