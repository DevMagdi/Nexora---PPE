import type { PPEClassInfo } from "@/types"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"

type Props = {
  items: PPEClassInfo[]
  value: string[]
  onChange: (next: string[]) => void
}

export default function PpeClassPicker({ items, value, onChange }: Props) {
  function toggleKey(key: string) {
    if (value.includes(key)) {
      onChange(value.filter((x) => x !== key))
    } else {
      onChange(Array.from(new Set([...value, key])))
    }
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
              onClick={(e) => e.stopPropagation()}
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