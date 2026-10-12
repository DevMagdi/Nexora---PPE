import { AlertTriangle, CheckCircle2, X } from "lucide-react"
import type { ToastState } from "@/types"

interface ToastProps {
  toast: ToastState | null
  onClose: () => void
}

export default function Toast({ toast, onClose }: ToastProps) {
  if (!toast) return null
  const ok = toast.tone === "success"
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 bottom-5 z-[60] mx-auto w-fit max-w-[92vw] animate-fade-in-up"
    >
      <div
        className={`glass flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold shadow-2xl ring-1 ${
          ok ? "ring-success/40" : "ring-destructive/40"
        }`}
      >
        {ok ? (
          <CheckCircle2 className="size-4.5 shrink-0 text-success" />
        ) : (
          <AlertTriangle className="size-4.5 shrink-0 text-destructive" />
        )}
        <span>{toast.text}</span>
        <button
          type="button"
          aria-label="إغلاق"
          onClick={onClose}
          className="ms-1 rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X className="size-3.5" />
        </button>
      </div>
    </div>
  )
}
