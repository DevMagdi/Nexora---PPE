import { CheckCircle2, Circle } from "lucide-react"
import type { PPEClassInfo } from "@/types"

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

  function selectAll() {
    onChange(items.map((it) => it.key))
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          تم اختيار <strong className="font-bold text-foreground">{value.length}</strong> من{" "}
          {items.length} فئات
        </span>
        {value.length < items.length && (
          <button
            type="button"
            onClick={selectAll}
            className="font-bold text-primary hover:underline"
          >
            تحديد الكل
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {items.map((it) => {
          const checked = value.includes(it.key)
          return (
            <button
              key={it.key}
              type="button"
              role="checkbox"
              aria-checked={checked}
              onClick={() => toggleKey(it.key)}
              className={`flex min-h-11 w-full items-center gap-2.5 rounded-xl border px-3 py-2 text-start transition-all cursor-pointer ${
                checked
                  ? "border-primary/40 bg-primary-light text-foreground shadow-xs"
                  : "border-border/70 bg-card text-muted-foreground hover:border-primary/30 hover:bg-muted/40"
              }`}
            >
              {checked ? (
                <CheckCircle2 className="size-4 shrink-0 text-primary" />
              ) : (
                <Circle className="size-4 shrink-0 opacity-40" />
              )}
              <div className="min-w-0 flex-1 leading-tight">
                <div className="truncate text-xs font-bold text-foreground">{it.label_ar}</div>
                <div className="truncate text-[10px] text-muted-foreground" dir="ltr">
                  {it.label_en}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
