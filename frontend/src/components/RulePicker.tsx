import type { RuleKey } from "@/types"
import { RULE_LABEL } from "@/lib/formatters"

export default function RulePicker({
  value,
  onChange,
  disabled = false,
}: {
  value: RuleKey[]
  onChange: (value: RuleKey[]) => void
  disabled?: boolean
}) {
  return (
    <fieldset disabled={disabled}>
      <legend className="field-label">معدات الوقاية المطلوب رصدها</legend>
      <div className="flex flex-wrap gap-2">
        {(Object.keys(RULE_LABEL) as RuleKey[]).map((key) => (
          <label
            key={key}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs ${value.includes(key) ? "border-primary/50 bg-accent text-primary" : "border-border text-muted-foreground"}`}
          >
            <input
              type="checkbox"
              className="size-3.5 accent-primary"
              checked={value.includes(key)}
              onChange={(event) =>
                onChange(
                  event.target.checked ? [...value, key] : value.filter((item) => item !== key),
                )
              }
            />
            {RULE_LABEL[key]}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
