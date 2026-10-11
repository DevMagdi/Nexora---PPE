import { useEffect, useRef, useState } from "react"
import { getPPEClassesMeta } from "@/lib/api"
import type { PPEClassInfo } from "@/types"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { AlertTriangle, RefreshCw } from "lucide-react"

type Props = {
  value: string[]
  onChange: (next: string[]) => void
}

export default function PpeClassPicker({ value, onChange }: Props) {
  const [items, setItems] = useState<PPEClassInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)

  // عشان مانطبقش default_enabled كل مرة ونبوّظ اختيار المستخدم
  const didInitDefault = useRef(false)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(false)

    ;(async () => {
      try {
        const meta = await getPPEClassesMeta()
        if (!mounted) return

        setItems(meta.items)

        // طبّق default مرة واحدة فقط لو مفيش اختيار
        if (!didInitDefault.current && (!value || value.length === 0)) {
          didInitDefault.current = true
          onChange(meta.default_enabled ?? [])
        }
      } catch {
        if (mounted) setError(true)
      } finally {
        if (mounted) setLoading(false)
      }
    })()

    return () => {
      mounted = false
    }
    // intentionally only refetch when attempt changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt])

  function toggleKey(key: string) {
    if (value.includes(key)) {
      onChange(value.filter((x) => x !== key))
    } else {
      onChange(Array.from(new Set([...value, key])))
    }
  }

  if (loading) return <div className="text-sm text-muted-foreground">جاري تحميل عناصر PPE...</div>

  if (error) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive-light px-3 py-2.5 text-sm">
        <span className="flex items-center gap-2 text-destructive-foreground">
          <AlertTriangle className="size-4 shrink-0" /> تعذّر تحميل قائمة معدات الوقاية
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 shrink-0 gap-1.5 rounded-lg text-xs"
          onClick={() => setAttempt((a) => a + 1)}
        >
          <RefreshCw className="size-3" /> إعادة المحاولة
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {items.map((it) => {
        const checked = value.includes(it.key)
        const id = `ppe-${it.key}`

        return (
          <button
            key={it.key}
            type="button"
            onClick={() => toggleKey(it.key)}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-start hover:bg-muted/40"
          >
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={() => toggleKey(it.key)}
              onClick={(e) => e.stopPropagation()} // يمنع double toggle
            />

            <Label htmlFor={id} className="flex cursor-pointer items-center gap-2">
              <span>{it.label_ar}</span>
              <span className="text-xs text-muted-foreground">({it.label_en})</span>
            </Label>
          </button>
        )
      })}
    </div>
  )
}