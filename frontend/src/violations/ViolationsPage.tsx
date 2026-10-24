import { useState } from "react"
import { ChevronLeft, ChevronRight, Download, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ErrorPanel, InlineError, Loading } from "@/components/Feedback"
import EventTable from "@/violations/EventTable"
import { useViolations } from "@/hooks/useNexora"
import { downloadViolationsCsv } from "@/lib/api"
import { NEGATIVE_LABELS, num } from "@/lib/formatters"
import type { Camera, Violation, ViolationFilters } from "@/types"

export default function ViolationsPage({
  from,
  to,
  siteId,
  cameras,
  canOperate,
  pendingId,
  onResolve,
  onEvidence,
}: {
  from?: string
  to?: string
  siteId?: number
  cameras: Camera[]
  canOperate: boolean
  pendingId?: number
  onResolve: (id: number) => void
  onEvidence: (event: Violation) => void
}) {
  const [page, setPage] = useState(1)
  const [camera, setCamera] = useState("")
  const [type, setType] = useState("")
  const [status, setStatus] = useState<"all" | "open" | "resolved">("all")
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<unknown>(null)
  const filters: ViolationFilters = {
    page,
    page_size: 25,
    site_id: siteId,
    camera_id: camera ? Number(camera) : undefined,
    violation_type: type || undefined,
    status,
    from,
    to,
  }
  const query = useViolations(filters)
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / 25))
  async function exportCsv() {
    setExporting(true)
    setExportError(null)
    try {
      const { page: _page, page_size: _size, ...params } = filters
      await downloadViolationsCsv(params)
    } catch (error) {
      setExportError(error)
    } finally {
      setExporting(false)
    }
  }
  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border p-5">
        <div className="flex flex-wrap gap-3">
          <div>
            <label className="field-label" htmlFor="event-camera">
              الكاميرا
            </label>
            <select
              id="event-camera"
              className="field !w-auto min-w-36"
              value={camera}
              onChange={(e) => {
                setCamera(e.target.value)
                setPage(1)
              }}
            >
              <option value="">كل الكاميرات</option>
              {cameras
                .filter((item) => !siteId || item.site_id === siteId)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="field-label" htmlFor="event-type">
              نوع المخالفة
            </label>
            <select
              id="event-type"
              className="field !w-auto min-w-36"
              value={type}
              onChange={(e) => {
                setType(e.target.value)
                setPage(1)
              }}
            >
              <option value="">كل المعدات</option>
              {Object.entries(NEGATIVE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field-label" htmlFor="event-status">
              الحالة
            </label>
            <select
              id="event-status"
              className="field !w-auto min-w-32"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as typeof status)
                setPage(1)
              }}
            >
              <option value="all">كل الحالات</option>
              <option value="open">مفتوحة</option>
              <option value="resolved">تمت المعالجة</option>
            </select>
          </div>
        </div>
        <Button
          variant="outline"
          disabled={exporting || !query.data?.total}
          onClick={() => void exportCsv()}
        >
          {exporting ? <Loader2 /> : <Download />}تصدير CSV
        </Button>
      </div>
      {exportError ? (
        <div className="p-6">
          <InlineError error={exportError} />
        </div>
      ) : null}
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorPanel error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <EventTable
            items={query.data.items}
            cameras={cameras}
            canOperate={canOperate}
            pendingId={pendingId}
            onResolve={onResolve}
            onEvidence={onEvidence}
          />
          <div className="flex items-center justify-between border-t border-border p-4 text-xs text-muted-foreground">
            <span>
              {num(query.data.total)} حدث · صفحة {num(page)} من {num(totalPages)}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="icon"
                aria-label="الصفحة السابقة"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                <ChevronRight />
              </Button>
              <Button
                variant="outline"
                size="icon"
                aria-label="الصفحة التالية"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => value + 1)}
              >
                <ChevronLeft />
              </Button>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
