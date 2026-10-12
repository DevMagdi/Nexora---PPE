import { AlertTriangle, CheckCircle2, X } from "lucide-react"
import type { ToastState } from "@/types/app"

export function Toast({ toast, onClose }: { toast: ToastState | null; onClose: () => void }) {
  if (!toast) return null
  const success = toast.tone === "success"
  return (
    <div role={success ? "status" : "alert"} aria-live={success ? "polite" : "assertive"} className="fixed inset-x-0 bottom-4 z-[60] mx-auto w-fit max-w-[92vw] px-2 animate-fade-in-up">
      <div className={`glass flex items-center gap-2.5 rounded-xl border bg-card/90 px-4 py-3 text-sm font-semibold shadow-floating ${success ? "border-success/30" : "border-destructive/30"}`}>
        {success ? <CheckCircle2 className="size-4 shrink-0 text-success" /> : <AlertTriangle className="size-4 shrink-0 text-destructive" />}
        <span>{toast.text}</span>
        <button type="button" aria-label="إغلاق الإشعار" onClick={onClose} className="tap-target ms-1 rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground">
          <X className="size-4" />
        </button>
      </div>
    </div>
  )
}
