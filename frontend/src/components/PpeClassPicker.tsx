import { useEffect, useState } from "react"
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

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(false)

    ;(async () => {
      try {
        const meta = await getPPEClassesMeta()
        if (!mounted) return

        setItems(meta.items)

        // default_enabled من الباك إند
        if (!value || value.length === 0) {
          onChange(meta.default_enabled)
        }
      } catch {
        // ✅ قبل كده كان فشل الطلب بيسيب الشاشة عالقة على "جاري
        // التحميل..." للأبد من غير catch. دلوقتي بنعرض رسالة واضحة
        // مع زرار "إعادة المحاولة".
        if (mounted) setError(true)
      } finally {
        if (mounted) setLoading(false)
      }
    })()

    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt])

  function setChecked(key: string, checked: boolean) {
    if (checked) onChange(Array.from(new Set([...value, key])))
    else onChange(value.filter((x) => x !== key))
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
        return (
          <div key={it.key} className="flex items-center gap-2">
            <Checkbox checked={checked} onCheckedChange={(v) => setChecked(it.key, Boolean(v))} />
            <Label className="flex items-center gap-2">
              <span>{it.label_ar}</span>
              <span className="text-xs text-muted-foreground">({it.label_en})</span>
            </Label>
          </div>
        )
      })}
    </div>
  )
}