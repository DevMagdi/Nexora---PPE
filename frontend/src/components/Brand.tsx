export default function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3 text-primary" aria-label="Nexora Industrial Safety">
      <svg aria-hidden="true" width="35" height="39" viewBox="0 0 35 39" fill="none">
        <path
          d="M17.5 1.5 33 10v18L17.5 37 2 28V10L17.5 1.5Z"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <path
          d="M10 26V13l15 13V13M10 13l15 13"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinejoin="round"
        />
      </svg>
      {!compact && (
        <div dir="ltr">
          <div className="latin text-[22px] font-semibold tracking-[.14em] leading-tight">
            NEXORA<span className="ms-1 text-[8px] align-top">®</span>
          </div>
          <div className="latin mt-1 text-[7px] tracking-[.29em] text-muted-foreground">
            INDUSTRIAL SAFETY INTELLIGENCE
          </div>
        </div>
      )}
    </div>
  )
}
