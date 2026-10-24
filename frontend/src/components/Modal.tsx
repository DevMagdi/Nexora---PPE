import { useRef, type ReactNode } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export default function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean
  onClose: () => void
  title: string
  description: string
  children: ReactNode
  wide?: boolean
}) {
  const returnFocus = useRef<HTMLElement | null>(null)
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose()
      }}
    >
      <DialogContent
        dir="rtl"
        className={wide ? "max-w-4xl" : ""}
        onOpenAutoFocus={() => {
          returnFocus.current =
            document.activeElement instanceof HTMLElement ? document.activeElement : null
        }}
        onCloseAutoFocus={(event) => {
          // Dialogs are opened by application state rather than DialogTrigger.
          // Restore keyboard focus explicitly after closing the focus trap.
          event.preventDefault()
          const target = returnFocus.current?.isConnected
            ? returnFocus.current
            : document.getElementById("main-content")
          target?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle className="!text-primary pe-5">{title}</DialogTitle>
          <DialogDescription className="leading-relaxed">{description}</DialogDescription>
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  )
}
