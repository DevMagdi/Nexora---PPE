import { lazy, Suspense } from "react"
import { LoaderCircle } from "lucide-react"
import { useDashboardController } from "@/hooks/useDashboardController"
import { AppShell } from "@/layout/AppShell"
import { FramePreviewDialog } from "@/shared/FramePreviewDialog"
import { Toast } from "@/shared/Toast"

const OverviewScreen = lazy(() => import("@/dashboard/OverviewScreen").then((module) => ({ default: module.OverviewScreen })))
const LiveScreen = lazy(() => import("@/dashboard/LiveScreen").then((module) => ({ default: module.LiveScreen })))
const CamerasScreen = lazy(() => import("@/cameras/CamerasScreen").then((module) => ({ default: module.CamerasScreen })))
const ViolationsScreen = lazy(() => import("@/violations/ViolationsScreen").then((module) => ({ default: module.ViolationsScreen })))

export default function App() {
  const app = useDashboardController()
  const screen = app.tab === "overview" ? (
    <OverviewScreen
      headline={app.headline}
      range={app.range}
      rangeLabel={app.rangeLabel}
      onRangeChange={app.changeRange}
      isMedicalView={app.isMedicalView}
      medicalNegatives={app.medicalNegatives}
      activeLiveStatus={app.activeLiveStatus}
      selectedCamera={app.selectedCamera}
      compliance={app.compliance}
      totalCameras={app.totalCameras}
      runningCameras={app.runningCount}
      camerasLoading={app.camerasLoading}
      hourAlerts={app.hourAlerts}
      openViolations={app.openViolations}
      alertsByCameraCount={app.alertsByCamera.size}
      overviewRaw={app.overviewData}
      overviewList={app.overviewList}
      coreCount={app.coreCount}
      overviewCapped={app.overviewCapped}
      overviewLoading={app.overviewLoading}
      overviewError={app.overviewError}
      onRetryOverview={app.refetchOverview}
      series={app.series}
      pieData={app.pieData}
      ppeLabels={app.ppeLabels}
      cameraName={app.cameraName}
      now={app.now}
      onOpenFrame={app.openFrame}
      onShowViolations={() => app.setTab("violations")}
    />
  ) : app.tab === "live" ? (
    <LiveScreen
      cameras={app.cameraList}
      camerasLoading={app.camerasLoading}
      camerasError={app.camerasError}
      selectedCamera={app.selectedCamera}
      ppeLabels={app.ppeLabels}
      counts={app.activeCounts}
      status={app.activeLiveStatus}
      compliance={app.compliance}
      canOperate={app.canOperate}
      pending={app.cameraPending}
      onRetryCameras={app.refetchCameras}
      onSelectCamera={app.selectCamera}
      onStart={() => app.selectedCamera && app.toggleCamera(app.selectedCamera)}
      onStop={() => app.selectedCamera && app.toggleCamera(app.selectedCamera)}
      onGoCameras={() => app.setTab("cameras")}
      onStreamReady={app.handleStreamReady}
      onStreamLost={app.handleStreamLost}
    />
  ) : app.tab === "cameras" ? (
    <CamerasScreen
      cameras={app.cameraList}
      orderedCameras={app.orderedCameras}
      camerasLoading={app.camerasLoading}
      camerasError={app.camerasError}
      canOperate={app.canOperate}
      ppeLabels={app.ppeLabels}
      previewAllowed={app.previewAllowed}
      togglingCameraId={app.togglingCameraId}
      alertsByCamera={app.alertsByCamera}
      onRetry={app.refetchCameras}
      onToggle={app.toggleCamera}
      onWatch={(camera) => app.selectCamera(camera.id)}
      onDeleted={app.onCameraDeleted}
      notify={app.notify}
    />
  ) : (
    <ViolationsScreen
      key={`${app.range}|${app.cameraFilter}|${app.typeFilter}`}
      cameras={app.cameraList}
      violations={app.violationsData}
      isLoading={app.violationsLoading}
      isError={app.violationsError}
      cameraFilter={app.cameraFilter}
      onCameraFilterChange={app.setCameraFilter}
      typeInput={app.typeInput}
      onTypeInputChange={app.setTypeInput}
      knownTypes={app.knownTypes}
      ppeLabels={app.ppeLabels}
      rangeLabel={app.rangeLabel}
      exporting={app.exporting}
      onExport={app.onExport}
      onRetry={app.refetchViolations}
      cameraName={app.cameraName}
      now={app.now}
      canOperate={app.canOperate}
      resolvingViolationId={app.resolvingViolationId}
      onResolve={app.resolveViolation}
      onOpenFrame={app.openFrame}
    />
  )

  return (
    <AppShell
      activeTab={app.tab}
      onTabChange={app.setTab}
      range={app.range}
      onRangeChange={app.changeRange}
      dark={app.dark}
      onToggleTheme={() => app.setDark((current) => !current)}
      user={app.user}
      health={app.health}
      healthLoading={app.healthLoading}
      healthError={app.healthError}
      onRetryHealth={app.refetchHealth}
      cameraCount={app.totalCameras}
      runningCount={app.runningCount}
      unseen={app.unseen}
      violations={app.overviewData}
      violationsError={app.overviewError}
      onRetryViolations={app.refetchOverview}
      recentViolations={app.overviewList}
      rangeLabel={app.rangeLabel}
      ppeLabels={app.ppeLabels}
      cameraName={app.cameraName}
      now={app.now}
      onMarkSeen={app.onMarkSeen}
      onOpenFrame={app.openFrame}
      onViewAllViolations={() => app.setTab("violations")}
      onLogout={app.handleLogout}
    >
      <Suspense fallback={<ScreenLoading />}>{screen}</Suspense>
      <FramePreviewDialog url={app.frameUrl} onClose={app.closeFrame} />
      <Toast toast={app.toast} onClose={app.clearToast} />
    </AppShell>
  )
}

function ScreenLoading() {
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-7xl flex-col justify-center gap-4" role="status" aria-live="polite">
      <div className="flex items-center gap-3 text-sm font-semibold text-muted-foreground"><LoaderCircle className="size-4 animate-spin text-primary" /> جارٍ تجهيز مساحة العمل...</div>
      <div className="skeleton-shimmer h-32 rounded-2xl" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"><div className="skeleton-shimmer h-36 rounded-2xl" /><div className="skeleton-shimmer h-36 rounded-2xl" /><div className="skeleton-shimmer h-36 rounded-2xl" /></div>
    </div>
  )
}
