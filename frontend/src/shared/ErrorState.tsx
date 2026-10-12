import { RefreshCw, WifiOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import EmptyState from "@/shared/EmptyState"

interface ErrorStateProps {
  title: string
  desc?: string
  onRetry: () => void
  compact?: boolean
}

export default function ErrorState({
  title,
  desc = "تحقق من اتصال الخادم ثم أعد المحاولة.",
  onRetry,
  compact = false,
}: ErrorStateProps) {
  return (
    <EmptyState
      compact={compact}
      icon={<WifiOff className="size-6 text-destructive" />}
      title={title}
      desc={desc}
      action={
        <Button type="button" variant="outline" onClick={onRetry} className="min-h-11 gap-2 rounded-xl px-4">
          <RefreshCw className="size-4" /> إعادة المحاولة
        </Button>
      }
    />
  )
}
