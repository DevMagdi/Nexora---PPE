import { useMemo, useState } from "react"
import { ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Camera, Violation, ViolationListResponse } from "@/types"
import { isCoreType, TABLE_PAGE_SIZE } from "@/lib/domain"
import type { ViolationStatusFilter } from "@/types/app"
import { EmptyState } from "@/shared/EmptyState"
import { ErrorState } from "@/shared/ErrorState"
import { PremiumCard } from "@/shared/PremiumCard"
import { ViolationFilters } from "@/violations/ViolationFilters"
import { ViolationCard, ViolationTableRow } from "@/violations/ViolationRow"

interface Props {
  cameras: Camera[]
  violations: ViolationListResponse | undefined
  isLoading: boolean
  isError: boolean
  cameraFilter: number | "all"
  onCameraFilterChange: (filter: number | "all") => void
  typeInput: string
  onTypeInputChange: (value: string) => void
  knownTypes: string[]
  ppeLabels: Map<string, string>
  rangeLabel: string
  exporting: boolean
  onExport: () => void
  onRetry: () => void
  cameraName: (id: number) => string
  now: number
  canOperate: boolean
  resolvingViolationId: number | null
  onResolve: (violation: Violation) => void
  onOpenFrame: (url?: string | null) => void
}

export function ViolationsScreen({ cameras, violations, isLoading, isError, cameraFilter, onCameraFilterChange, typeInput, onTypeInputChange, knownTypes, ppeLabels, rangeLabel, exporting, onExport, onRetry, cameraName, now, canOperate, resolvingViolationId, onResolve, onOpenFrame }: Props) {
  const [showAllTypes, setShowAllTypes] = useState(false)
  const [statusFilter, setStatusFilter] = useState<ViolationStatusFilter>("all")
  const [page, setPage] = useState(1)
  const changeStatusFilter = (value: ViolationStatusFilter) => { setStatusFilter(value); setPage(1) }
  const changeTypeView = (value: boolean) => { setShowAllTypes(value); setPage(1) }

  const filtered = useMemo(() => (violations?.items ?? [])
    .filter((violation) => showAllTypes || isCoreType(violation.violation_type))
    .filter((violation) => statusFilter === "all" || (statusFilter === "resolved" ? violation.is_resolved : !violation.is_resolved)),
  [violations, showAllTypes, statusFilter])
  const pageCount = Math.max(1, Math.ceil(filtered.length / TABLE_PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const pageItems = filtered.slice((safePage - 1) * TABLE_PAGE_SIZE, safePage * TABLE_PAGE_SIZE)
  const isCapped = (violations?.total ?? 0) > (violations?.items.length ?? 0)

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <ViolationFilters
        rangeLabel={rangeLabel}
        cameras={cameras}
        cameraFilter={cameraFilter}
        onCameraFilterChange={onCameraFilterChange}
        typeInput={typeInput}
        onTypeInputChange={onTypeInputChange}
        knownTypes={knownTypes}
        ppeLabels={ppeLabels}
        showAllTypes={showAllTypes}
        onShowAllTypesChange={changeTypeView}
        statusFilter={statusFilter}
        onStatusFilterChange={changeStatusFilter}
        exporting={exporting}
        onExport={onExport}
      />

      <PremiumCard className="overflow-hidden">
        {isError && !violations ? (
          <ErrorState title="تعذّر تحميل المخالفات" onRetry={onRetry} />
        ) : isLoading && !violations ? (
          <div className="space-y-3 p-4 sm:p-5" aria-label="جارٍ تحميل المخالفات">{Array.from({ length: 5 }, (_, index) => <div key={index} className="skeleton-shimmer h-[92px] rounded-xl" />)}</div>
        ) : filtered.length === 0 ? (
          <EmptyState className="m-4" icon={<ShieldCheck className="size-5 text-success" />} title="لا توجد نتائج مطابقة" desc="جرّب تغيير الفلاتر أو توسيع النطاق الزمني." />
        ) : (
          <>
            <div className="divide-y divide-border/70 p-3 sm:p-4 2xl:hidden">
              {pageItems.map((violation) => <ViolationCard key={violation.id} violation={violation} ppeLabels={ppeLabels} cameraName={cameraName} now={now} canOperate={canOperate} pending={resolvingViolationId === violation.id} onResolve={onResolve} onOpenFrame={onOpenFrame} />)}
            </div>
            <div className="hidden overflow-x-auto 2xl:block">
              <table className="w-full min-w-[1000px] whitespace-nowrap text-start text-sm">
                <thead className="border-b border-border bg-muted/60 text-xs font-semibold text-muted-foreground">
                  <tr>
                    <th className="p-3.5 text-start">الدليل المرئي</th>
                    <th className="p-3.5 text-start">التاريخ والوقت</th>
                    <th className="p-3.5 text-start">نوع المخالفة</th>
                    <th className="p-3.5 text-start">الكاميرا</th>
                    <th className="p-3.5 text-start">ثقة الكشف</th>
                    <th className="p-3.5 text-start">الحالة</th>
                    <th className="p-3.5 text-end"><span className="sr-only">الإجراءات</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/70">
                  {pageItems.map((violation) => <ViolationTableRow key={violation.id} violation={violation} ppeLabels={ppeLabels} cameraName={cameraName} now={now} canOperate={canOperate} pending={resolvingViolationId === violation.id} onResolve={onResolve} onOpenFrame={onOpenFrame} />)}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/70 bg-muted/20 p-3.5 text-xs text-muted-foreground sm:p-4">
              <span className="tabular-nums">عرض {filtered.length ? (safePage - 1) * TABLE_PAGE_SIZE + 1 : 0}–{Math.min(safePage * TABLE_PAGE_SIZE, filtered.length)} من {filtered.length}{isCapped ? "+ (المعروض حتى 200)" : ""} سجل</span>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" className="min-h-11 rounded-lg px-3 text-xs" disabled={safePage <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>السابق</Button>
                <span className="min-w-20 text-center tabular-nums">صفحة {safePage} من {pageCount}</span>
                <Button type="button" variant="outline" className="min-h-11 rounded-lg px-3 text-xs" disabled={safePage >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>التالي</Button>
              </div>
            </div>
          </>
        )}
      </PremiumCard>
    </div>
  )
}
