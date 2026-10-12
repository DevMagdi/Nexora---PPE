import { ChevronDown, Download, Loader2, ShieldAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { violationLabel } from "@/lib/formatters"
import SegToggle from "@/shared/SegToggle"
import type { Camera } from "@/types"

interface ViolationFiltersProps {
  rangeLabel: string
  totalCams: number
  cameraList: Camera[]
  camFilter: number | "all"
  onCamFilterChange: (next: number | "all") => void
  typeInput: string
  onTypeInputChange: (next: string) => void
  knownTypes: string[]
  ppeLabels: Map<string, string>
  showAllTypes: boolean
  onShowAllTypesChange: (next: boolean) => void
  exporting: boolean
  onExport: () => void
}

export default function ViolationFilters({
  rangeLabel,
  totalCams,
  cameraList,
  camFilter,
  onCamFilterChange,
  typeInput,
  onTypeInputChange,
  knownTypes,
  ppeLabels,
  showAllTypes,
  onShowAllTypesChange,
  exporting,
  onExport,
}: ViolationFiltersProps) {
  return (
    <div className="card-premium flex flex-col justify-between gap-4 rounded-2xl border border-border/60 p-5 lg:flex-row lg:items-center">
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-destructive/15 p-2">
          <ShieldAlert className="size-5 text-destructive" />
        </div>
        <div>
          <h2 className="text-lg font-bold leading-tight text-foreground">
            سجل الحوادث والمخالفات
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            كل الانتهاكات المرصودة تلقائيًا في {rangeLabel}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <select
            aria-label="تصفية حسب الكاميرا"
            className="h-10 min-w-[160px] cursor-pointer appearance-none rounded-xl border border-input bg-card py-2 pe-9 ps-3 text-sm shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-2 focus:ring-primary/25"
            value={camFilter}
            onChange={(e) =>
              onCamFilterChange(e.target.value === "all" ? "all" : Number(e.target.value))
            }
          >
            <option value="all">جميع الكاميرات ({totalCams})</option>
            {cameraList.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        </div>

        <div className="relative">
          <select
            aria-label="تصفية حسب نوع المخالفة"
            className="h-10 min-w-[160px] cursor-pointer appearance-none rounded-xl border border-input bg-card py-2 pe-9 ps-3 text-sm shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-2 focus:ring-primary/25"
            value={typeInput}
            onChange={(e) => onTypeInputChange(e.target.value)}
          >
            <option value="">كل الأنواع</option>
            {knownTypes.map((t) => (
              <option key={t} value={t}>
                {violationLabel(t, ppeLabels)}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        </div>

        <SegToggle
          checked={showAllTypes}
          onChange={onShowAllTypesChange}
          labelOn="كل الأنواع"
          labelOff="معدات الوقاية"
        />

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-1.5 rounded-xl"
          disabled={exporting}
          onClick={onExport}
        >
          {exporting ? <Loader2 className="size-3.5 animate-spin" /> : <Download size={14} />}
          تصدير CSV
        </Button>
      </div>
    </div>
  )
}
