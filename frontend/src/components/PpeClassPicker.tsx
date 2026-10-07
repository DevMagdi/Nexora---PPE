import { useEffect, useState } from "react"
import { getPPEClassesMeta } from "@/lib/api"
import type { PPEClassInfo } from "@/types"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"

type Props = {
  value: string[]
  onChange: (next: string[]) => void
}

export default function PpeClassPicker({ value, onChange }: Props) {
  const [items, setItems] = useState<PPEClassInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    ;(async () => {
      const meta = await getPPEClassesMeta()
      if (!mounted) return

      setItems(meta.items)

      // default_enabled من الباك إند
      if (!value || value.length === 0) {
        onChange(meta.default_enabled)
      }

      setLoading(false)
    })()

    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function setChecked(key: string, checked: boolean) {
    if (checked) onChange(Array.from(new Set([...value, key])))
    else onChange(value.filter((x) => x !== key))
  }

  if (loading) return <div className="text-muted-foreground">جاري تحميل عناصر PPE...</div>

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