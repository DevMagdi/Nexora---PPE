import { AlertTriangle, Cctv, ShieldAlert, Users } from "lucide-react"
import ComplianceRing from "@/dashboard/ComplianceRing"
import MedicalStatusCard from "@/dashboard/MedicalStatusCard"
import StatCard from "@/dashboard/StatCard"
import type { Camera, LiveCounts, LiveStatus } from "@/types"

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
  overviewCount: number
  overviewCapped: boolean
  coreCount: number
  camerasLoading: boolean
  totalCams: number
  runningCount: number
  hourAlerts: number
  alertsCameraCount: number
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
  overviewCount,
  overviewCapped,
  coreCount,
  camerasLoading,
  totalCams,
  runningCount,
  hourAlerts,
  alertsCameraCount,
}: HeroStripProps) {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold leading-tight">{headline}</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          ملخص الالتزام والتنبيهات خلال {rangeLabel}
        </p>
      </div>

      <div className="stagger grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-4">
          {isMedicalView ? (
            <MedicalStatusCard
              count={medicalNegatives}
              live={activeLiveStatus === "open"}
              hint={
                selectedCamera?.is_running
                  ? `لحظيًا من «${selectedCamera.name}»`
                  : "شغّل كاميرا لعرض الحالة اللحظية"
              }
            />
          ) : (
            <ComplianceRing
              value={compliance}
              live={activeLiveStatus === "open"}
              hint={
                selectedCamera?.is_running
                  ? `لحظيًا من «${selectedCamera.name}»`
                  : "شغّل كاميرا لعرض النسبة اللحظية"
              }
            />
          )}
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:col-span-8 lg:gap-8">
          <StatCard
            label={isMedicalView ? "مخالفات ظاهرة في الكادر" : "عمال تحت المراقبة الآن"}
            value={isMedicalView ? medicalNegatives : liveWorkers}
            icon={
              isMedicalView ? (
                <ShieldAlert className="size-5 stroke-[2.5]" />
              ) : (
                <Users className="size-5 stroke-[2.5]" />
              )
            }
            tone={isMedicalView ? "destructive" : "info"}
            live={activeLiveStatus === "open"}
            hint={
              selectedCamera?.is_running
                ? isMedicalView
                  ? `${activeCounts.no_mask ?? 0} كمامة · ${activeCounts.no_gloves ?? 0} قفازات · ${activeCounts.no_goggles ?? 0} نظارات · ${activeCounts.no_cap ?? 0} غطاء رأس`
                  : `${activeCounts.hardhat ?? 0} خوذة · ${activeCounts.vest ?? 0} سترة`
                : "لا يوجد بث نشط"
            }
          />
          <StatCard
            label={`مخالفات ${rangeLabel}`}
            value={hasOverviewRaw ? overviewCount : undefined}
            plus={overviewCapped}
            icon={<ShieldAlert className="size-5 stroke-[2.5]" />}
            tone="warning"
            hint={hasOverviewRaw ? `${coreCount} منها تخص معدات الوقاية الأساسية` : "—"}
          />
          <StatCard
            label="كاميرات تعمل الآن"
            value={camerasLoading && totalCams === 0 ? undefined : runningCount}
            icon={<Cctv className="size-5 stroke-[2.5]" />}
            tone="primary"
            hint={`من ${totalCams} كاميرا مُسجّلة`}
          />
          <StatCard
            label="تنبيهات آخر ساعة"
            value={hasOverviewRaw ? hourAlerts : undefined}
            icon={<AlertTriangle className="size-5 stroke-[2.5]" />}
            tone="destructive"
            hint={
              hasOverviewRaw
                ? alertsCameraCount > 0
                  ? `على ${alertsCameraCount} كاميرا`
                  : "لا توجد تنبيهات نشطة"
                : "—"
            }
          />
        </div>
      </div>
    </div>
  )
}
