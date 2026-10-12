import { ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { TABLE_PAGE_SIZE, VIOLATIONS_FETCH_LIMIT } from "@/lib/formatters"
import Card from "@/shared/Card"
import EmptyState from "@/shared/EmptyState"
import ErrorState from "@/shared/ErrorState"
import SkeletonBlock from "@/shared/SkeletonBlock"
import ViolationFilters from "@/violations/ViolationFilters"
import ViolationRow, { ViolationMobileCard } from "@/violations/ViolationRow"
import type { Camera, Violation, ViolationStatusFilter } from "@/types"

interface ViolationsTableProps {
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
  violationsError: boolean
  hasViolationsRaw: boolean
  rawItemsCount: number
  loadingV: boolean
  onRetryViolations: () => void
  filteredList: Violation[]
  pageItems: Violation[]
  safePage: number
  pageCount: number
  onPageChange: (nextPage: number) => void
  cameraName: (id: number) => string
  now: number
  canOperate: boolean
  resolvingViolationId: number | null
  onOpenFrame: (url?: string | null) => void
  onResolveViolation: (v: Violation) => void
}

export default function ViolationsTable({
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
  violationsError,
  hasViolationsRaw,
  rawItemsCount,
  loadingV,
  onRetryViolations,
  filteredList,
  pageItems,
  safePage,
  pageCount,
  onPageChange,
  cameraName,
  now,
  canOperate,
  resolvingViolationId,
  onOpenFrame,
  onResolveViolation,
}: ViolationsTableProps) {
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <ViolationFilters
        rangeLabel={rangeLabel}
        totalCams={totalCams}
        cameraList={cameraList}
        camFilter={camFilter}
        onCamFilterChange={onCamFilterChange}
        typeInput={typeInput}
        onTypeInputChange={onTypeInputChange}
        statusFilter={statusFilter}
        onStatusFilterChange={onStatusFilterChange}
        statusCounts={statusCounts}
        knownTypes={knownTypes}
        ppeLabels={ppeLabels}
        showAllTypes={showAllTypes}
        onShowAllTypesChange={onShowAllTypesChange}
        exporting={exporting}
        onExport={onExport}
      />

      {/* ─── Mobile Cards View (< 768px) ─── */}
      <div className="space-y-3 md:hidden">
        {violationsError && !hasViolationsRaw && (
          <ErrorState compact title="تعذّر تحميل المخالفات" onRetry={onRetryViolations} />
        )}
        {loadingV && !hasViolationsRaw && !violationsError && (
          <div className="space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="card-premium space-y-3 border border-border/60 p-4">
                <div className="flex items-center gap-3">
                  <SkeletonBlock className="size-16 rounded-xl" />
                  <div className="flex-1 space-y-2">
                    <SkeletonBlock className="h-4 w-32 rounded" />
                    <SkeletonBlock className="h-3 w-24 rounded" />
                  </div>
                </div>
                <SkeletonBlock className="h-10 w-full rounded-xl" />
              </div>
            ))}
          </div>
        )}
        {!loadingV && !violationsError && filteredList.length === 0 && (
          <EmptyState
            compact
            icon={<ShieldCheck className="size-6 text-success" />}
            title="لا توجد نتائج مطابقة"
            desc="جرّب تغيير الفلاتر أو توسيع النطاق الزمني."
          />
        )}
        {pageItems.map((v) => (
          <ViolationMobileCard
            key={v.id}
            violation={v}
            ppeLabels={ppeLabels}
            cameraName={cameraName(v.camera_id)}
            now={now}
            canOperate={canOperate}
            resolvePending={resolvingViolationId === v.id}
            onOpenFrame={onOpenFrame}
            onResolve={onResolveViolation}
          />
        ))}
      </div>

      {/* ─── Desktop Table View (>= 768px) ─── */}
      <Card className="hidden overflow-hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-start text-sm">
            <thead className="border-b border-border bg-muted/60 text-xs font-bold text-muted-foreground">
              <tr>
                <th className="p-4 text-start">الدليل المرئي</th>
                <th className="p-4 text-start">التوقيت</th>
                <th className="p-4 text-start">نوع المخالفة</th>
                <th className="p-4 text-start">الكاميرا</th>
                <th className="p-4 text-start">ثقة الكشف</th>
                <th className="p-4 text-start">الحالة</th>
                <th className="p-4 text-end">
                  <span className="sr-only">إجراءات</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/70">
              {violationsError && !hasViolationsRaw && (
                <tr>
                  <td colSpan={7} className="p-6">
                    <ErrorState
                      compact
                      title="تعذّر تحميل المخالفات"
                      onRetry={onRetryViolations}
                    />
                  </td>
                </tr>
              )}

              {loadingV && !hasViolationsRaw && !violationsError && (
                <>
                  {Array.from({ length: 5 }, (_, i) => (
                    <tr key={i}>
                      <td colSpan={7} className="p-4">
                        <div className="flex items-center gap-4">
                          <SkeletonBlock className="h-11 w-16 rounded-xl" />
                          <div className="flex-1 space-y-2">
                            <SkeletonBlock className="h-4 w-48 rounded" />
                            <SkeletonBlock className="h-3 w-24 rounded" />
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </>
              )}

              {!loadingV && !violationsError && filteredList.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-6">
                    <EmptyState
                      compact
                      icon={<ShieldCheck className="size-6 text-success" />}
                      title="لا توجد نتائج مطابقة"
                      desc="جرّب تغيير الفلاتر أو توسيع النطاق الزمني."
                    />
                  </td>
                </tr>
              )}

              {pageItems.map((v) => (
                <ViolationRow
                  key={v.id}
                  violation={v}
                  ppeLabels={ppeLabels}
                  cameraName={cameraName(v.camera_id)}
                  now={now}
                  canOperate={canOperate}
                  resolvePending={resolvingViolationId === v.id}
                  onOpenFrame={onOpenFrame}
                  onResolve={onResolveViolation}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ─── Pagination Footer ─── */}
      <Card className="flex flex-wrap items-center justify-between gap-3 p-4 text-xs text-muted-foreground">
        <span className="tabular-nums font-medium">
          {filteredList.length === 0
            ? "لا توجد سجلات"
            : `عرض ${(safePage - 1) * TABLE_PAGE_SIZE + 1} إلى ${Math.min(
                safePage * TABLE_PAGE_SIZE,
                filteredList.length,
              )} من ${filteredList.length}${
                rawItemsCount >= VIOLATIONS_FETCH_LIMIT ? "+" : ""
              } سجل`}
        </span>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-h-9 rounded-xl px-3 text-xs font-semibold"
            disabled={safePage <= 1}
            onClick={() => onPageChange(Math.max(1, safePage - 1))}
          >
            السابق
          </Button>
          <span className="px-2 font-bold tabular-nums text-foreground">
            صفحة {safePage} من {pageCount}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-h-9 rounded-xl px-3 text-xs font-semibold"
            disabled={safePage >= pageCount}
            onClick={() => onPageChange(Math.min(pageCount, safePage + 1))}
          >
            التالي
          </Button>
        </div>
      </Card>
    </div>
  )
}
