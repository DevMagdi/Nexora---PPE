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
    onChange(value.includes(key) ? value.filter((item) => item !== key) : Array.from(new Set([...value, key])))
  }

  return (
    <fieldset className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
      <legend className="sr-only">قواعد معدات الوقاية</legend>
      {items.map((item) => {
        const checked = value.includes(item.key)
        const id = `ppe-${item.key}`
        return (
          <div key={item.key} className="flex min-h-11 items-center gap-2 rounded-xl border border-transparent px-2.5 transition-colors hover:border-border/70 hover:bg-muted/50">
            <Checkbox id={id} checked={checked} onCheckedChange={() => toggleKey(item.key)} aria-label={item.label_ar} />
            <Label htmlFor={id} className="flex min-h-11 flex-1 cursor-pointer items-center gap-1.5 text-sm">
              <span className="font-medium">{item.label_ar}</span>
              <span className="text-[11px] text-muted-foreground">({item.label_en})</span>
            </Label>
          </div>
        )
      })}
    </fieldset>
  )
}
