import { AlertTriangle, Cctv, ShieldAlert } from "lucide-react"
import type { Violation, ViolationListResponse } from "@/types"
import type { LiveStatus, RangeKey, ViolationChartPoint, ViolationTypePoint } from "@/types/app"
import { ChartsSection } from "@/dashboard/ChartsSection"
import { ComplianceRing } from "@/dashboard/ComplianceRing"
import { MedicalStatusCard } from "@/dashboard/MedicalStatusCard"
import { RecentAlerts } from "@/dashboard/RecentAlerts"
import { StatCard } from "@/shared/StatCard"
import { PageHeader } from "@/shared/PageHeader"

interface Props {
  headline: string
  range: RangeKey
  rangeLabel: string
  onRangeChange: (range: RangeKey) => void
  isMedicalView: boolean
  medicalNegatives: number | undefined
  activeLiveStatus: LiveStatus
  selectedCamera: { id: number; name: string; is_running: boolean } | null
  compliance: number | undefined
  totalCameras: number
  runningCameras: number
  camerasLoading: boolean
  hourAlerts: number
  openViolations: number
  alertsByCameraCount: number
  overviewRaw: ViolationListResponse | undefined
  overviewList: Violation[]
  coreCount: number
  overviewCapped: boolean
  overviewLoading: boolean
  overviewError: boolean
  onRetryOverview: () => void
  series: ViolationChartPoint[]
  pieData: ViolationTypePoint[]
  ppeLabels: Map<string, string>
  cameraName: (id: number) => string
  now: number
  onOpenFrame: (url?: string | null) => void
  onShowViolations: () => void
}

export function OverviewScreen({ headline, range, rangeLabel, onRangeChange, isMedicalView, medicalNegatives, activeLiveStatus, selectedCamera, compliance, totalCameras, runningCameras, camerasLoading, hourAlerts, openViolations, alertsByCameraCount, overviewRaw, overviewList, coreCount, overviewCapped, overviewLoading, overviewError, onRetryOverview, series, pieData, ppeLabels, cameraName, now, onOpenFrame, onShowViolations }: Props) {
  const live = activeLiveStatus === "open"
  const hasData = Boolean(overviewRaw)
  const subtitle = selectedCamera?.is_running ? `المؤشرات اللحظية من «${selectedCamera.name}» مع سجل الفترة المحددة.` : `ملخص الالتزام والتنبيهات خلال ${rangeLabel}.`

  return (
    <div className="mx-auto max-w-7xl space-y-7 sm:space-y-8">
      <PageHeader eyebrow="مركز القيادة" title={headline} description={subtitle} />

      <section aria-label="مؤشرات العمليات" className="stagger grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12 lg:gap-5">
        <div className="sm:col-span-2 lg:col-span-4">
          {isMedicalView ? (
            <MedicalStatusCard count={medicalNegatives} live={live} hint={selectedCamera?.is_running ? `مباشر من «${selectedCamera.name}»` : "شغّل كاميرا لعرض الحالة اللحظية"} />
          ) : (
            <ComplianceRing value={compliance} live={live} hint={selectedCamera?.is_running ? `مباشر من «${selectedCamera.name}»` : "شغّل كاميرا لعرض النسبة اللحظية"} />
          )}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:col-span-2 sm:grid-cols-2 lg:col-span-8 lg:grid-cols-2 lg:gap-5">
          <StatCard
            label={`مخالفات ${rangeLabel}`}
            value={overviewRaw?.total}
            icon={<ShieldAlert className="size-5" />}
            tone="warning"
            loading={overviewLoading && !overviewRaw}
            hint={overviewRaw ? overviewCapped ? `${coreCount} من أحدث 200 سجل تخص معدات الوقاية الأساسية` : `${coreCount} منها تخص معدات الوقاية الأساسية` : "يتم تحديث سجل المخالفات"}
          />
          <StatCard
            label="كاميرات تعمل الآن"
            value={runningCameras}
            icon={<Cctv className="size-5" />}
            tone="primary"
            loading={camerasLoading && totalCameras === 0}
            hint={`من ${totalCameras} كاميرا مسجلة`}
          />
          <StatCard
            label="مخالفات مفتوحة"
            value={overviewRaw ? openViolations : undefined}
            icon={<AlertTriangle className="size-5" />}
            tone="destructive"
            loading={overviewLoading && !overviewRaw}
            hint={overviewRaw ? overviewCapped ? "من أحدث 200 سجل؛ قد توجد حالات أقدم" : "تحتاج إلى مراجعة أو معالجة" : "بانتظار تحميل الحالة"}
          />
          <StatCard
            label="تنبيهات آخر ساعة"
            value={overviewRaw ? hourAlerts : undefined}
            icon={<AlertTriangle className="size-5" />}
            tone="info"
            loading={overviewLoading && !overviewRaw}
            hint={overviewRaw ? overviewCapped ? "الإحصاء من أحدث 200 سجل" : alertsByCameraCount > 0 ? `على ${alertsByCameraCount} كاميرا` : "لا توجد تنبيهات جديدة" : "بانتظار تحميل التنبيهات"}
          />
        </div>
      </section>

      <ChartsSection
        range={range}
        onRangeChange={onRangeChange}
        series={series}
        pieData={pieData}
        totalCount={overviewRaw?.total ?? overviewList.length}
        isCapped={overviewCapped}
        isLoading={overviewLoading}
        isError={overviewError}
        hasData={hasData}
        rangeLabel={rangeLabel}
        onRetry={onRetryOverview}
      />

      <RecentAlerts
        violations={overviewList}
        ppeLabels={ppeLabels}
        cameraName={cameraName}
        now={now}
        isLoading={overviewLoading}
        isError={overviewError}
        hasData={hasData}
        rangeLabel={rangeLabel}
        onRetry={onRetryOverview}
        onOpenFrame={onOpenFrame}
        onShowAll={onShowViolations}
      />
    </div>
  )
}
