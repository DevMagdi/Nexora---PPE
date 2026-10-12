import { ChevronDown, Download, Loader2, ShieldAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { violationLabel } from "@/lib/formatters"
import SegToggle from "@/shared/SegToggle"
import type { Camera, ViolationStatusFilter } from "@/types"

interface ViolationFiltersProps {
  rangeLabel: string
  totalCams: number
  cameraList: Camera[]
  camFilter: number | "all"
  onCamFilterChange: (next: number | "all") => void
  typeInput: string
  onTypeInputChange: (next: string) => void
  statusFilter: ViolationStatusFilter
  onStatusFilterChange: (next: ViolationStatusFilter) => void
  statusCounts: { all: number; open: number; resolved: number }
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
  statusFilter,
  onStatusFilterChange,
  statusCounts,
  knownTypes,
  ppeLabels,
  showAllTypes,
  onShowAllTypesChange,
  exporting,
  onExport,
}: ViolationFiltersProps) {
  return (
    <div className="space-y-4">
      <div className="card-premium flex flex-col justify-between gap-4 rounded-2xl border border-border/70 p-5 lg:flex-row lg:items-center">
        <div className="flex items-center gap-3.5">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-destructive-light text-destructive">
            <ShieldAlert className="size-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold leading-tight text-foreground sm:text-xl">
              سجل الحوادث والمخالفات
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              كل الانتهاكات المرصودة والموثّقة تلقائيًا في {rangeLabel}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <select
              aria-label="تصفية حسب الكاميرا"
              className="h-10 min-w-[160px] cursor-pointer appearance-none rounded-xl border border-input bg-card py-2 pe-9 ps-3 text-xs font-semibold shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-2 focus:ring-primary/25"
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
              className="h-10 min-w-[160px] cursor-pointer appearance-none rounded-xl border border-input bg-card py-2 pe-9 ps-3 text-xs font-semibold shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-2 focus:ring-primary/25"
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
            className="min-h-10 gap-1.5 rounded-xl px-3.5 text-xs font-semibold"
            disabled={exporting}
            onClick={onExport}
          >
            {exporting ? <Loader2 className="size-3.5 animate-spin" /> : <Download size={14} />}
            تصدير CSV
          </Button>
        </div>
      </div>

      {/* ─── Quick Filter Chips (Status + Type) ─── */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onStatusFilterChange("all")}
          className={`chip-filter ${statusFilter === "all" ? "chip-filter-active" : ""}`}
        >
          <span>الكل</span>
          <span className="rounded-full bg-card/80 px-1.5 py-0.2 text-[11px] tabular-nums">
            {statusCounts.all}
          </span>
        </button>
        <button
          type="button"
          onClick={() => onStatusFilterChange("open")}
          className={`chip-filter ${statusFilter === "open" ? "chip-filter-active" : ""}`}
        >
          <span className="size-2 rounded-full bg-destructive" />
          <span>غير معالجة</span>
          <span className="rounded-full bg-card/80 px-1.5 py-0.2 text-[11px] tabular-nums">
            {statusCounts.open}
          </span>
        </button>
        <button
          type="button"
          onClick={() => onStatusFilterChange("resolved")}
          className={`chip-filter ${statusFilter === "resolved" ? "chip-filter-active" : ""}`}
        >
          <span className="size-2 rounded-full bg-success" />
          <span>تمت المعالجة</span>
          <span className="rounded-full bg-card/80 px-1.5 py-0.2 text-[11px] tabular-nums">
            {statusCounts.resolved}
          </span>
        </button>

        {knownTypes.length > 0 && (
          <>
            <div className="mx-1 hidden h-4 w-px bg-border sm:block" />
            {knownTypes.slice(0, 5).map((t) => {
              const active = typeInput === t
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => onTypeInputChange(active ? "" : t)}
                  className={`chip-filter ${active ? "chip-filter-active" : ""}`}
                >
                  {violationLabel(t, ppeLabels)}
                </button>
              )
            })}
          </>
        )}
      </div>
    </div>
  )
}
