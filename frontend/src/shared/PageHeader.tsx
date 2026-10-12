import type { ReactNode } from "react"

interface PageHeaderProps {
  title: string
  subtitle?: string
  badge?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
}

export default function PageHeader({ title, subtitle, badge, icon, actions }: PageHeaderProps) {
  return (
    <div className="card-premium flex flex-col justify-between gap-4 rounded-2xl border border-border/70 p-6 sm:flex-row sm:items-center">
      <div className="flex items-start gap-3.5">
        {icon && (
          <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary-light text-primary ring-1 ring-primary/15">
            {icon}
          </div>
        )}
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">{title}</h2>
            {badge}
          </div>
          {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2.5">{actions}</div>}
    </div>
  )
}
