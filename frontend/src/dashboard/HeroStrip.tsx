import {
  Activity,
  AlertTriangle,
  Cctv,
  HardHat,
  MonitorPlay,
  ShieldAlert,
  Stethoscope,
  Users,
} from "lucide-react"
import ComplianceRing from "@/dashboard/ComplianceRing"
import MedicalStatusCard from "@/dashboard/MedicalStatusCard"
import StatCard from "@/dashboard/StatCard"
import { formatRelative } from "@/lib/formatters"
import LiveDot from "@/shared/LiveDot"
import type { Camera, LiveCounts, LiveStatus, Violation } from "@/types"

interface HeroStripProps {
  headline: string
  rangeLabel: string
  isMedicalView: boolean
  medicalNegatives: number | undefined
  compliance: number | undefined
  liveWorkers: number | undefined
  activeLiveStatus: LiveStatus
  selectedCamera: Camera | null
  activeCounts: LiveCounts
  hasOverviewRaw: boolean
  overviewLoading?: boolean
  overviewCount: number
  overviewCapped: boolean
  coreCount: number
  openViolationsCount?: number
  lastViolation?: Violation | null
  now: number
  camerasLoading: boolean
  totalCams: number
  runningCount: number
  hourAlerts: number
  alertsCameraCount: number
  onGoLive?: () => void
  onGoViolations?: () => void
}

export default function HeroStrip({
  headline,
  rangeLabel,
  isMedicalView,
  medicalNegatives,
  compliance,
  liveWorkers,
  activeLiveStatus,
  selectedCamera,
  activeCounts,
  hasOverviewRaw,
  overviewLoading = false,
  overviewCount,
  overviewCapped,
  coreCount,
  openViolationsCount = 0,
  lastViolation = null,
  now,
  camerasLoading,
  totalCams,
  runningCount,
  hourAlerts,
  alertsCameraCount,
  onGoLive,
  onGoViolations,
}: HeroStripProps) {
  const isStreaming = activeLiveStatus === "open"
  const lastAlertText = lastViolation
    ? `آخر رصد ${formatRelative(lastViolation.timestamp, now)}`
    : alertsCameraCount > 0
      ? `على ${alertsCameraCount} كاميرا`
      : "لا توجد تنبيهات نشطة"

  return (
    <div className="space-y-6">
      {/* ─── Executive Hero Operations Strip Banner ─── */}
      <div className="hero-strip-surface p-6 sm:p-7">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-light px-3 py-1 text-xs font-bold text-primary">
                <LiveDot tone="success" active={runningCount > 0} />
                <span>مركز القيادة والعمليات</span>
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-card/80 px-3 py-1 text-xs font-semibold text-muted-foreground">
                {isMedicalView ? (
                  <>
                    <Stethoscope className="size-3.5 text-info" /> نمط الرصد الطبي
                  </>
                ) : (
                  <>
                    <HardHat className="size-3.5 text-warning" /> نمط الإنشاءات والمصانع
                  </>
                )}
              </span>
              {selectedCamera?.is_running && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-success-light px-3 py-1 text-xs font-bold text-success-foreground">
                  <Activity className="size-3.5" />
                  <span>الكشف الهجين نشط · {selectedCamera.name}</span>
                </span>
              )}
            </div>

            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              {headline}
            </h2>
            <p className="text-sm text-muted-foreground">
              ملخص الأداء التنفيذي ومؤشرات الامتثال والتنبيهات خلال{" "}
              <strong className="font-semibold text-foreground">{rangeLabel}</strong>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {onGoLive && (
              <button type="button" onClick={onGoLive} className="btn-cta">
                <MonitorPlay className="size-4" />
                <span>المراقبة المباشرة</span>
              </button>
            )}
            {onGoViolations && openViolationsCount > 0 && (
              <button type="button" onClick={onGoViolations} className="btn-ghost">
                <ShieldAlert className="size-4 text-destructive" />
                <span>{openViolationsCount} مخالفة مفتوحة</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ─── KPI Operations Grid ─── */}
      <div className="stagger grid grid-cols-1 gap-5 lg:grid-cols-12 lg:gap-6">
        <div className="lg:col-span-4">
          {isMedicalView ? (
            <MedicalStatusCard
              count={medicalNegatives}
              live={isStreaming}
              hint={
                selectedCamera?.is_running
                  ? `قراءة حية من «${selectedCamera.name}»`
                  : "شغّل كاميرا لعرض الحالة اللحظية"
              }
            />
          ) : (
            <ComplianceRing
              value={compliance}
              live={isStreaming}
              hint={
                selectedCamera?.is_running
                  ? `قراءة حية من «${selectedCamera.name}»`
                  : "شغّل كاميرا لعرض النسبة اللحظية"
              }
            />
          )}
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:col-span-8 lg:gap-6">
          <StatCard
            label={isMedicalView ? "مخالفات ظاهرة في الكادر" : "عمال تحت المراقبة الآن"}
            value={isMedicalView ? medicalNegatives : liveWorkers}
            icon={
              isMedicalView ? (
                <ShieldAlert className="size-5 stroke-[2.2]" />
              ) : (
                <Users className="size-5 stroke-[2.2]" />
              )
            }
            tone={isMedicalView ? "destructive" : "info"}
            live={isStreaming}
            hint={
              selectedCamera?.is_running
                ? isMedicalView
                  ? `${activeCounts.no_mask ?? 0} كمامة · ${activeCounts.no_gloves ?? 0} قفازات · ${activeCounts.no_goggles ?? 0} نظارات · ${activeCounts.no_cap ?? 0} غطاء رأس`
                  : `${activeCounts.hardhat ?? 0} خوذة · ${activeCounts.vest ?? 0} سترة واقية`
                : "لا يوجد بث نشط حاليًا"
            }
          />
          <StatCard
            label={`مخالفات ${rangeLabel}`}
            value={hasOverviewRaw ? overviewCount : undefined}
            loading={overviewLoading && !hasOverviewRaw}
            plus={overviewCapped}
            icon={<ShieldAlert className="size-5 stroke-[2.2]" />}
            tone="warning"
            hint={
              hasOverviewRaw
                ? `${coreCount} مخالفة أساسية · ${openViolationsCount} غير معالجة`
                : "—"
            }
          />
          <StatCard
            label="الكاميرات النشطة الآن"
            value={camerasLoading && totalCams === 0 ? undefined : runningCount}
            loading={camerasLoading && totalCams === 0}
            icon={<Cctv className="size-5 stroke-[2.2]" />}
            tone="primary"
            hint={`من إجمالي ${totalCams} كاميرا مُسجّلة بالنظام`}
          />
          <StatCard
            label="تنبيهات آخر ساعة"
            value={hasOverviewRaw ? hourAlerts : undefined}
            loading={overviewLoading && !hasOverviewRaw}
            icon={<AlertTriangle className="size-5 stroke-[2.2]" />}
            tone="destructive"
            hint={hasOverviewRaw ? lastAlertText : "—"}
          />
        </div>
      </div>
    </div>
  )
}
