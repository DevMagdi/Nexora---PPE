import { ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { TABLE_PAGE_SIZE, VIOLATIONS_FETCH_LIMIT } from "@/lib/formatters"
import Card from "@/shared/Card"
import EmptyState from "@/shared/EmptyState"
import ErrorState from "@/shared/ErrorState"
import SkeletonBlock from "@/shared/SkeletonBlock"
import ViolationFilters from "@/violations/ViolationFilters"
import ViolationRow from "@/violations/ViolationRow"
import type { Camera, Violation } from "@/types"

interface ViolationsTableProps {
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
        knownTypes={knownTypes}
        ppeLabels={ppeLabels}
        showAllTypes={showAllTypes}
        onShowAllTypesChange={onShowAllTypesChange}
        exporting={exporting}
        onExport={onExport}
      />

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-start text-sm">
            <thead className="border-b border-border bg-muted/60 text-xs font-semibold text-muted-foreground">
              <tr>
                <th className="p-4 text-start">الدليل المرئي</th>
                <th className="p-4 text-start">التاريخ والوقت</th>
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
                          <SkeletonBlock className="h-10 w-14 rounded-xl" />
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
                  canOperate={canOperate}
                  resolvePending={resolvingViolationId === v.id}
                  onOpenFrame={onOpenFrame}
                  onResolve={onResolveViolation}
                />
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/40 bg-muted/15 p-4 text-xs text-muted-foreground">
          <span className="tabular-nums">
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
              className="h-7 rounded-lg text-[11px]"
              disabled={safePage <= 1}
              onClick={() => onPageChange(Math.max(1, safePage - 1))}
            >
              السابق
            </Button>
            <span className="tabular-nums">
              صفحة {safePage} من {pageCount}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 rounded-lg text-[11px]"
              disabled={safePage >= pageCount}
              onClick={() => onPageChange(Math.min(pageCount, safePage + 1))}
            >
              التالي
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
