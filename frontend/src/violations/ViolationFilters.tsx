import { Download, Loader2, ShieldAlert } from "lucide-react"
import type { Camera } from "@/types"
import type { ViolationStatusFilter } from "@/types/app"
import { SegmentedToggle } from "@/shared/SegmentedToggle"
import { violationLabel } from "@/lib/domain"
import { PremiumCard } from "@/shared/PremiumCard"

interface Props {
  rangeLabel: string
  cameras: Camera[]
  cameraFilter: number | "all"
  onCameraFilterChange: (filter: number | "all") => void
  typeInput: string
  onTypeInputChange: (value: string) => void
  knownTypes: string[]
  ppeLabels: Map<string, string>
  showAllTypes: boolean
  onShowAllTypesChange: (value: boolean) => void
  statusFilter: ViolationStatusFilter
  onStatusFilterChange: (value: ViolationStatusFilter) => void
  exporting: boolean
  onExport: () => void
}

const statusOptions: Array<{ value: ViolationStatusFilter; label: string }> = [
  { value: "all", label: "الكل" },
  { value: "open", label: "مفتوحة" },
  { value: "resolved", label: "معالجة" },
]

export function ViolationFilters({ rangeLabel, cameras, cameraFilter, onCameraFilterChange, typeInput, onTypeInputChange, knownTypes, ppeLabels, showAllTypes, onShowAllTypesChange, statusFilter, onStatusFilterChange, exporting, onExport }: Props) {
  return (
    <PremiumCard className="space-y-4 p-4 sm:p-5">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-xl bg-destructive-light text-destructive"><ShieldAlert className="size-5" /></span>
          <div>
            <h2 className="text-base font-bold">سجل المخالفات</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">الانتهاكات المرصودة خلال {rangeLabel}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <label className="sr-only" htmlFor="violation-camera-filter">تصفية حسب الكاميرا</label>
          <select id="violation-camera-filter" className="min-h-11 min-w-[150px] rounded-xl border border-input bg-card px-3 text-sm shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30" value={cameraFilter} onChange={(event) => onCameraFilterChange(event.target.value === "all" ? "all" : Number(event.target.value))}>
            <option value="all">جميع الكاميرات ({cameras.length})</option>
            {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
          </select>
          <label className="sr-only" htmlFor="violation-type-filter">تصفية حسب نوع المخالفة</label>
          <select id="violation-type-filter" className="min-h-11 min-w-[150px] rounded-xl border border-input bg-card px-3 text-sm shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30" value={typeInput} onChange={(event) => onTypeInputChange(event.target.value)}>
            <option value="">كل الأنواع</option>
            {knownTypes.map((type) => <option key={type} value={type}>{violationLabel(type, ppeLabels)}</option>)}
          </select>
          <SegmentedToggle checked={showAllTypes} onChange={onShowAllTypesChange} labelOn="كل الفئات" labelOff="معدات الوقاية" ariaLabel="نوع المخالفات المعروضة" />
          <button type="button" onClick={onExport} disabled={exporting} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-semibold transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50">
            {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
            تصدير CSV
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
        <span className="me-1 text-xs font-semibold text-muted-foreground">الحالة:</span>
        {statusOptions.map((option) => (
          <button key={option.value} type="button" aria-pressed={statusFilter === option.value} onClick={() => onStatusFilterChange(option.value)} className={`min-h-11 rounded-full border px-4 text-xs font-semibold transition-colors ${statusFilter === option.value ? "border-primary/30 bg-primary-light text-primary" : "border-border bg-card text-muted-foreground hover:bg-muted"}`}>
            {option.label}
          </button>
        ))}
      </div>
    </PremiumCard>
  )
}
