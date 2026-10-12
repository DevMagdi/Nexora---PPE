import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"

export function FramePreviewDialog({ url, onClose }: { url: string | null; onClose: () => void }) {
  return (
    <Dialog open={url !== null} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-5xl overflow-hidden rounded-2xl border-border bg-background p-0 shadow-floating">
        <DialogHeader className="border-b border-border bg-card/90 p-4 text-start">
          <DialogTitle className="text-sm font-bold text-foreground">معاينة الدليل المرئي</DialogTitle>
          <DialogDescription className="text-xs">اللقطة التي رصد فيها النظام المخالفة</DialogDescription>
        </DialogHeader>
        <div className="flex min-h-[min(60vh,420px)] items-center justify-center bg-slate-950 p-4 sm:p-6">
          {url && <img src={url} className="max-h-[75vh] max-w-full rounded-xl border border-white/10 object-contain" alt="لقطة المخالفة" />}
        </div>
      </DialogContent>
    </Dialog>
  )
}
