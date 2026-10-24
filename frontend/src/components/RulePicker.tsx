import type { RuleKey } from "@/types"
import { RULE_LABEL } from "@/lib/formatters"

export default function RulePicker({
  value,
  onChange,
  disabled = false,
  supportedNegativeRules,
}: {
  value: RuleKey[]
  onChange: (value: RuleKey[]) => void
  disabled?: boolean
  supportedNegativeRules?: RuleKey[] | null
}) {
  return (
    <fieldset disabled={disabled}>
      <legend className="field-label">معدات الوقاية المطلوب رصدها</legend>
      <div className="flex flex-wrap gap-2">
        {(Object.keys(RULE_LABEL) as RuleKey[]).map((key) => (
          <label
            key={key}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-3 text-xs ${value.includes(key) ? "border-border bg-accent text-primary" : "border-border text-muted-foreground"}`}
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
            <span>{RULE_LABEL[key]}</span>
            {supportedNegativeRules && !supportedNegativeRules.includes(key) && (
              <span className="text-[10px] text-muted-foreground">عرض فقط</span>
            )}
          </label>
        ))}
      </div>
      {supportedNegativeRules &&
        Object.keys(RULE_LABEL).some((key) => !supportedNegativeRules.includes(key as RuleKey)) && (
          <p className="source-help mt-3">
            «عرض فقط»: الفئة السالبة غير موجودة في الوزن؛ تنبيه القاعدة معطّل، ويظل كشف المعدات
            الموجب متاحًا إن دعمه الوزن.
          </p>
        )}
    </fieldset>
  )
}
