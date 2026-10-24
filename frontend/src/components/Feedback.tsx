import type { ReactNode } from "react"
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getErrorMessage } from "@/lib/utils"

export function Loading({ label = "جارٍ تحميل البيانات…" }: { label?: string }) {
  return (
    <div role="status" className="empty-state">
      <Loader2 />
      <p>{label}</p>
    </div>
  )
}
export function Empty({
  title,
  description,
  action,
  icon,
}: {
  title: string
  description: string
  action?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-icon" aria-hidden="true">
        {icon ?? <Inbox />}
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  )
}
export function ErrorPanel({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="empty-state">
      <span className="empty-state-icon" aria-hidden="true">
        <AlertTriangle className="!text-destructive" />
      </span>
      <h3>تعذّر تحميل البيانات</h3>
      <p>{getErrorMessage(error)}</p>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry}>
          <RefreshCw />
          إعادة المحاولة
        </Button>
      )}
    </div>
  )
}
export function InlineError({ error }: { error: unknown }) {
  return error ? (
    <p role="alert" className="notice notice-error">
      {getErrorMessage(error)}
    </p>
  ) : null
}
