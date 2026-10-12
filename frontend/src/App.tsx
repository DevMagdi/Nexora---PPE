import { useCallback, useEffect, useMemo, useState } from "react"
import AddCameraForm from "@/cameras/AddCameraForm"
import CameraGrid from "@/cameras/CameraGrid"
import ConfirmDialog from "@/components/ConfirmDialog"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import ChartsSection from "@/dashboard/ChartsSection"
import HeroStrip from "@/dashboard/HeroStrip"
import LiveViewSection from "@/dashboard/LiveStage"
import {
  useCameras,
  useDeleteCamera,
  useHealth,
  useMe,
  usePPEClassesMeta,
  useResolveViolation,
  useStartCamera,
  useStopCamera,
  useViolations,
} from "@/hooks/useNexora"
import { useLiveCameraSocket, useMediaQuery, useTheme } from "@/hooks/useUiHooks"
import AppShell from "@/layout/AppShell"
import { downloadViolationsCsv, logout, refreshMediaSession, resolveFrameUrl } from "@/lib/api"
import {
  cameraProfile,
  computeCompliance,
  DAY,
  HOUR,
  isCoreType,
  iso,
  liveMetrics,
  LOCALE,
  MAX_GRID_PREVIEWS,
  parseTs,
  ROLE_LABEL,
  SECTOR_LABEL,
  TAB_TITLES,
  TABLE_PAGE_SIZE,
  VIOLATIONS_FETCH_LIMIT,
  violationLabel,
} from "@/lib/formatters"
import { getErrorMessage } from "@/lib/utils"
import Toast from "@/shared/Toast"
import type {
  Camera,
  RangeKey,
  TabKey,
  ToastState,
  Violation,
  ViolationStatusFilter,
} from "@/types"
import ViolationsTable from "@/violations/ViolationsTable"

export default function App() {
  const isMobile = useMediaQuery("(max-width: 1023.98px)")
  const [dark, setDark] = useTheme()

  const { data: meUser } = useMe()
  const {
    data: health,
    isLoading: healthLoading,
    isError: healthError,
    refetch: refetchHealth,
  } = useHealth()
  const {
    data: cameras,
    isLoading: camerasLoading,
    isError: camerasError,
    refetch: refetchCameras,
  } = useCameras()
  const { data: ppeMetaC } = usePPEClassesMeta("construction")
  const { data: ppeMetaM } = usePPEClassesMeta("medical")

  const startMut = useStartCamera()
  const stopMut = useStopCamera()
  const deleteMut = useDeleteCamera()
  const resolveMut = useResolveViolation()

  const [tab, setTab] = useState<TabKey>("overview")
  const [range, setRange] = useState<RangeKey>("24h")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null)
  const [frameUrl, setFrameUrl] = useState<string | null>(null)
  const [showAllTypes, setShowAllTypes] = useState(false)
  const [statusFilter, setStatusFilter] = useState<ViolationStatusFilter>("all")
  const [cameraSearch, setCameraSearch] = useState("")
  const [typeInput, setTypeInput] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [camFilter, setCamFilter] = useState<number | "all">("all")
  const [page, setPage] = useState(1)
  const [addOpen, setAddOpen] = useState(false)
  const [exporting, setExporting] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null)

  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null)

  const [bellOpen, setBellOpen] = useState(false)
  const [seenByRange, setSeenByRange] = useState<Partial<Record<RangeKey, number>>>({})
  const [toast, setToast] = useState<ToastState | null>(null)
  const [now, setNow] = useState(() => Date.now())

  const meUserId = meUser?.id
  const mustChangePassword = meUser?.must_change_password
  const displayName = meUser?.username || "مستخدم Nexora"
  const displayRole = meUser
    ? `${ROLE_LABEL[meUser.role] ?? meUser.role} · ${SECTOR_LABEL[meUser.sector] ?? "حساب محلي"}`
    : "حساب محلي"
  const canOperate = meUser?.role === "admin" || meUser?.role === "operator"
  const serverOk = health?.status === "ok" && !healthError

  useEffect(() => {
    if (!meUserId || mustChangePassword) return
    const renew = () => void refreshMediaSession().catch(() => undefined)
    renew()
    const id = window.setInterval(renew, 5 * 60 * 1000)
    return () => window.clearInterval(id)
  }, [meUserId, mustChangePassword])

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])

  const { from, to } = useMemo(() => {
    const pad = 3 * HOUR
    return {
      from: new Date(now - (range === "24h" ? DAY : 7 * DAY) - pad),
      to: new Date(now + pad),
    }
  }, [range, now])
  const rangeLabel = range === "24h" ? "آخر 24 ساعة" : "آخر 7 أيام"

  const notify = useCallback(
    (tone: ToastState["tone"], text: string) => setToast({ id: Date.now(), tone, text }),
    [],
  )
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(t)
  }, [toast])

  useEffect(() => {
    const t = setTimeout(() => {
      setTypeFilter(typeInput.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(t)
  }, [typeInput])

  const ppeLabels = useMemo(() => {
    const m = new Map<string, string>()
    for (const it of [...(ppeMetaC?.items ?? []), ...(ppeMetaM?.items ?? [])]) {
      m.set(it.key, it.label_ar)
    }
    return m
  }, [ppeMetaC, ppeMetaM])

  const cameraList = useMemo(() => cameras ?? [], [cameras])
  const cameraName = useCallback(
    (id: number) => cameraList.find((c) => c.id === id)?.name ?? `كاميرا #${id}`,
    [cameraList],
  )
  const totalCams = cameraList.length
  const runningCams = useMemo(() => cameraList.filter((c) => c.is_running), [cameraList])
  const runningCount = runningCams.length

  const selectedCamera = useMemo(() => {
    if (cameraList.length === 0) return null
    if (selectedCameraId !== null) {
      const found = cameraList.find((c) => c.id === selectedCameraId)
      if (found) return found
    }
    return cameraList.find((c) => c.is_running) ?? cameraList[0]
  }, [cameraList, selectedCameraId])

  const {
    counts: activeCounts,
    activeLiveStatus,
    handleStreamReady,
    handleStreamLost,
  } = useLiveCameraSocket(selectedCamera)

  const filteredCams = useMemo(() => {
    const q = cameraSearch.trim().toLowerCase()
    if (!q) return cameraList
    return cameraList.filter((c) => c.name.toLowerCase().includes(q) || String(c.id).includes(q))
  }, [cameraList, cameraSearch])

  const togglingCamId: number | null = startMut.isPending
    ? (startMut.variables as number)
    : stopMut.isPending
      ? (stopMut.variables as number)
      : null

  const deletingCamId: number | null = deleteMut.isPending ? (deleteMut.variables as number) : null
  const resolvingViolationId: number | null = resolveMut.isPending
    ? (resolveMut.variables as number)
    : null

  const toggleCamera = useCallback(
    (c: Camera) => {
      const mut = c.is_running ? stopMut : startMut
      const verb = c.is_running ? "إيقاف" : "تشغيل"
      mut.mutate(c.id, {
        onSuccess: () => notify("success", `تم ${verb} «${c.name}» بنجاح`),
        onError: (error) =>
          notify("error", `${getErrorMessage(error, `تعذّر ${verb} «${c.name}»`)} · ${c.name}`),
      })
    },
    [startMut, stopMut, notify],
  )

  const selectCam = useCallback(
    (id: number) => {
      setSelectedCameraId(id)
      setTab("live")
      if (isMobile) setSidebarOpen(false)
    },
    [isMobile],
  )

  const openEdit = useCallback((c: Camera) => {
    setEditingCamera(c)
    setEditOpen(true)
  }, [])

  const askDelete = useCallback((c: Camera) => {
    setDeleteTarget(c)
    setDeleteOpen(true)
  }, [])

  const confirmDelete = useCallback(() => {
    if (!deleteTarget) return
    const c = deleteTarget
    deleteMut.mutate(c.id, {
      onSuccess: () => {
        setDeleteOpen(false)
        setDeleteTarget(null)
        if (selectedCameraId === c.id) setSelectedCameraId(null)
        notify("success", `تم حذف «${c.name}»`)
      },
      onError: () => notify("error", `تعذّر حذف «${c.name}»`),
    })
  }, [deleteMut, deleteTarget, notify, selectedCameraId])

  const resolveViolation = useCallback(
    (v: Violation) => {
      resolveMut.mutate(v.id, {
        onSuccess: () => notify("success", "تم تعليم المخالفة كمعالجة"),
        onError: () => notify("error", "تعذّر تعليم المخالفة كمعالجة"),
      })
    },
    [resolveMut, notify],
  )

  const handleLogout = useCallback(() => {
    void logout()
  }, [])

  const baseParams = useMemo(
    () => ({ page_size: VIOLATIONS_FETCH_LIMIT, from: iso(from), to: iso(to) }),
    [from, to],
  )
  const tableParams = useMemo(
    () => ({
      ...baseParams,
      ...(camFilter !== "all" ? { camera_id: camFilter } : {}),
      ...(typeFilter ? { violation_type: typeFilter } : {}),
    }),
    [baseParams, camFilter, typeFilter],
  )

  const isViolationsTab = tab === "violations"

  const {
    data: overviewData,
    isLoading: overviewLoading,
    isError: overviewError,
    refetch: refetchOverview,
  } = useViolations(baseParams)

  const {
    data: violationsData,
    isLoading: loadingV,
    isError: violationsError,
    refetch: refetchViolations,
  } = useViolations(tableParams, {
    enabled: isViolationsTab,
    refetchInterval: isViolationsTab ? 10_000 : false,
  })

  const byNewest = (a: Violation, b: Violation) =>
    parseTs(b.timestamp).getTime() - parseTs(a.timestamp).getTime()

  const overviewList = useMemo(
    () => [...(overviewData?.items ?? [])].sort(byNewest),
    [overviewData],
  )
  const coreCount = useMemo(
    () => overviewList.filter((v) => isCoreType(v.violation_type)).length,
    [overviewList],
  )
  const openViolationsCount = useMemo(
    () => overviewList.filter((v) => !v.is_resolved).length,
    [overviewList],
  )
  const overviewCapped = overviewList.length >= VIOLATIONS_FETCH_LIMIT

  const typeFilteredList = useMemo(
    () =>
      (violationsData?.items ?? [])
        .filter((v) => showAllTypes || isCoreType(v.violation_type))
        .sort(byNewest),
    [violationsData, showAllTypes],
  )

  const statusCounts = useMemo(() => {
    const open = typeFilteredList.filter((v) => !v.is_resolved).length
    const resolved = typeFilteredList.length - open
    return { all: typeFilteredList.length, open, resolved }
  }, [typeFilteredList])

  const filteredList = useMemo(() => {
    if (statusFilter === "open") return typeFilteredList.filter((v) => !v.is_resolved)
    if (statusFilter === "resolved") return typeFilteredList.filter((v) => v.is_resolved)
    return typeFilteredList
  }, [typeFilteredList, statusFilter])

  const pageCount = Math.max(1, Math.ceil(filteredList.length / TABLE_PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const pageItems = filteredList.slice(
    (safePage - 1) * TABLE_PAGE_SIZE,
    safePage * TABLE_PAGE_SIZE,
  )

  const knownTypes = useMemo(() => {
    const s = new Set<string>()
    for (const v of overviewList) s.add(v.violation_type)
    for (const v of violationsData?.items ?? []) s.add(v.violation_type)
    return [...s].sort()
  }, [overviewList, violationsData])

  const onExport = useCallback(async () => {
    setExporting(true)
    try {
      await downloadViolationsCsv({
        camera_id: camFilter === "all" ? undefined : camFilter,
        from: iso(from),
        to: iso(to),
        violation_type: typeFilter || undefined,
      })
      notify("success", "تم تنزيل ملف المخالفات")
    } catch {
      notify("error", "تعذّر تصدير المخالفات")
    } finally {
      setExporting(false)
    }
  }, [camFilter, from, to, typeFilter, notify])

  const series = useMemo(() => {
    const buckets = range === "24h" ? 24 : 7
    const size = range === "24h" ? HOUR : DAY
    const start = from.getTime() + 3 * HOUR
    const arr = Array.from({ length: buckets }, (_, i) => {
      const d = new Date(start + i * size)
      const label =
        range === "24h"
          ? d.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", hour12: false })
          : d.toLocaleDateString(LOCALE, { weekday: "short" })
      return { label, count: 0 }
    })
    for (const v of overviewList) {
      const idx = Math.floor((parseTs(v.timestamp).getTime() - start) / size)
      if (idx >= 0 && idx < buckets) arr[idx].count++
    }
    return arr
  }, [overviewList, from, range])

  const pieData = useMemo(() => {
    const m = new Map<string, number>()
    for (const v of overviewList) m.set(v.violation_type, (m.get(v.violation_type) ?? 0) + 1)
    return [...m.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([type, value]) => ({ name: violationLabel(type, ppeLabels), value }))
  }, [overviewList, ppeLabels])

  const activeProfile = selectedCamera
    ? cameraProfile(selectedCamera)
    : meUser?.sector === "medical"
      ? "medical"
      : "construction"
  const isMedicalView = activeProfile === "medical"
  const compliance = selectedCamera?.is_running
    ? computeCompliance(activeProfile, activeCounts)
    : undefined
  const liveWorkers =
    selectedCamera?.is_running && !isMedicalView ? activeCounts.person : undefined
  const medicalNegatives =
    selectedCamera?.is_running && isMedicalView
      ? (activeCounts.no_mask ?? 0) +
        (activeCounts.no_gloves ?? 0) +
        (activeCounts.no_goggles ?? 0) +
        (activeCounts.no_cap ?? 0)
      : undefined
  const overlayMetrics = liveMetrics(activeProfile, activeCounts)
  const camPending = selectedCamera !== null && togglingCamId === selectedCamera.id

  const effectiveSeenCount =
    seenByRange[range] ?? (overviewData ? overviewData.items.length : null)
  const unseen =
    effectiveSeenCount === null ? 0 : Math.max(0, overviewList.length - effectiveSeenCount)
  const toggleBell = () => {
    setBellOpen((o) => !o)
    setSeenByRange((prev) => ({ ...prev, [range]: overviewList.length }))
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSidebarOpen(false)
        setBellOpen(false)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const openFrame = useCallback((url?: string | null) => {
    const resolved = resolveFrameUrl(url)
    if (resolved) setFrameUrl(resolved)
  }, [])

  const orderedCams = useMemo(
    () => [...cameraList].sort((a, b) => Number(b.is_running) - Number(a.is_running)),
    [cameraList],
  )
  const previewAllowed = useMemo(() => {
    const ids = new Set<number>()
    for (const c of orderedCams) {
      if (c.is_running && ids.size < MAX_GRID_PREVIEWS) ids.add(c.id)
    }
    return ids
  }, [orderedCams])

  const alertsByCam = useMemo(() => {
    const m = new Map<number, number>()
    for (const v of overviewList) {
      if (isCoreType(v.violation_type) && now - parseTs(v.timestamp).getTime() < HOUR) {
        m.set(v.camera_id, (m.get(v.camera_id) ?? 0) + 1)
      }
    }
    return m
  }, [overviewList, now])
  const hourAlerts = useMemo(
    () => [...alertsByCam.values()].reduce((a, b) => a + b, 0),
    [alertsByCam],
  )

  const headline = isMedicalView
    ? medicalNegatives === undefined
      ? "شغّل كاميرا لبدء الرصد الطبي"
      : medicalNegatives === 0
        ? "لا توجد مخالفات ظاهرة في الكادر"
        : "توجد مخالفات معدات طبية في الكادر"
    : compliance === undefined
      ? "شغّل كاميرا لبدء قياس الالتزام"
      : compliance >= 90
        ? "الموقع ملتزم بمعدات الوقاية"
        : compliance >= 70
          ? "الالتزام يحتاج متابعة"
          : "الالتزام منخفض، تدخّل الآن"

  const crumbs =
    tab === "live" && selectedCamera ? [TAB_TITLES.live, selectedCamera.name] : [TAB_TITLES[tab]]

  return (
    <>
      <AppShell
        tab={tab}
        sidebarProps={{
          tab,
          onSelectTab: setTab,
          unseenCount: unseen,
          isMobile,
          sidebarOpen,
          onCloseMobile: () => setSidebarOpen(false),
          dark,
          health,
          healthLoading,
          healthError,
          onRetryHealth: () => void refetchHealth(),
          totalCams,
          runningCount,
          displayName,
          displayRole,
          onLogout: handleLogout,
        }}
        topbarProps={{
          tab,
          crumbs,
          isMobile,
          sidebarOpen,
          onOpenMobile: () => setSidebarOpen(true),
          range,
          onRangeChange: setRange,
          rangeLabel,
          now,
          dark,
          onToggleDark: () => setDark((d) => !d),
          unseenCount: unseen,
          bellOpen,
          onToggleBell: toggleBell,
          onCloseBell: () => setBellOpen(false),
          overviewError,
          hasOverviewRaw: Boolean(overviewData),
          onRetryOverview: () => void refetchOverview(),
          overviewList,
          ppeLabels,
          onOpenFrame: openFrame,
          onGoViolations: () => setTab("violations"),
          displayName,
          displayRole,
          serverOk,
          runningCount,
          onLogout: handleLogout,
        }}
      >
        {tab === "overview" && (
          <div className="mx-auto max-w-7xl space-y-8 lg:space-y-10">
            <HeroStrip
              headline={headline}
              rangeLabel={rangeLabel}
              isMedicalView={isMedicalView}
              medicalNegatives={medicalNegatives}
              compliance={compliance}
              liveWorkers={liveWorkers}
              activeLiveStatus={activeLiveStatus}
              selectedCamera={selectedCamera}
              activeCounts={activeCounts}
              hasOverviewRaw={Boolean(overviewData)}
              overviewLoading={overviewLoading}
              overviewCount={overviewList.length}
              overviewCapped={overviewCapped}
              coreCount={coreCount}
              openViolationsCount={openViolationsCount}
              lastViolation={overviewList[0] ?? null}
              now={now}
              camerasLoading={camerasLoading}
              totalCams={totalCams}
              runningCount={runningCount}
              hourAlerts={hourAlerts}
              alertsCameraCount={alertsByCam.size}
              onGoLive={() => setTab("live")}
              onGoViolations={() => {
                setStatusFilter("open")
                setTab("violations")
              }}
            />
            <ChartsSection
              range={range}
              onRangeChange={setRange}
              rangeLabel={rangeLabel}
              series={series}
              pieData={pieData}
              overviewList={overviewList}
              overviewCapped={overviewCapped}
              overviewLoading={overviewLoading}
              overviewError={overviewError}
              hasOverviewRaw={Boolean(overviewData)}
              onRetryOverview={() => void refetchOverview()}
              ppeLabels={ppeLabels}
              cameraName={cameraName}
              now={now}
              canOperate={canOperate}
              resolvingViolationId={resolvingViolationId}
              onResolveViolation={resolveViolation}
              onOpenFrame={openFrame}
              onGoViolations={() => setTab("violations")}
            />
          </div>
        )}

        {tab === "live" && (
          <LiveViewSection
            cameraSearch={cameraSearch}
            onCameraSearchChange={setCameraSearch}
            camerasError={camerasError}
            camerasLoading={camerasLoading}
            cameraList={cameraList}
            filteredCams={filteredCams}
            selectedCamera={selectedCamera}
            ppeLabels={ppeLabels}
            isMedicalView={isMedicalView}
            compliance={compliance}
            activeLiveStatus={activeLiveStatus}
            overlayMetrics={overlayMetrics}
            activeCounts={activeCounts}
            camPending={camPending}
            canOperate={canOperate}
            onRetryCameras={() => void refetchCameras()}
            onSelectCam={selectCam}
            onToggleCamera={toggleCamera}
            onGoCameras={() => setTab("cameras")}
            onAddFirstCamera={() => {
              setTab("cameras")
              setAddOpen(true)
            }}
            onStreamReady={handleStreamReady}
            onStreamLost={handleStreamLost}
          />
        )}

        {tab === "cameras" && (
          <CameraGrid
            cameraList={cameraList}
            orderedCams={orderedCams}
            runningCount={runningCount}
            camerasLoading={camerasLoading}
            camerasError={camerasError}
            onRetryCameras={() => void refetchCameras()}
            canOperate={canOperate}
            addOpen={addOpen}
            onAddOpenChange={setAddOpen}
            onAddSuccess={() => {
              setAddOpen(false)
              notify("success", "تمت إضافة الكاميرا بنجاح")
            }}
            ppeLabels={ppeLabels}
            previewAllowed={previewAllowed}
            togglingCamId={togglingCamId}
            deletingCamId={deletingCamId}
            alertsByCam={alertsByCam}
            onToggleCamera={toggleCamera}
            onSelectCam={selectCam}
            onOpenEdit={openEdit}
            onAskDelete={askDelete}
          />
        )}

        {tab === "violations" && (
          <ViolationsTable
            rangeLabel={rangeLabel}
            totalCams={totalCams}
            cameraList={cameraList}
            camFilter={camFilter}
            onCamFilterChange={(next) => {
              setCamFilter(next)
              setPage(1)
            }}
            typeInput={typeInput}
            onTypeInputChange={setTypeInput}
            statusFilter={statusFilter}
            onStatusFilterChange={(next) => {
              setStatusFilter(next)
              setPage(1)
            }}
            statusCounts={statusCounts}
            knownTypes={knownTypes}
            ppeLabels={ppeLabels}
            showAllTypes={showAllTypes}
            onShowAllTypesChange={(next) => {
              setShowAllTypes(next)
              setPage(1)
            }}
            exporting={exporting}
            onExport={() => void onExport()}
            violationsError={violationsError}
            hasViolationsRaw={Boolean(violationsData)}
            rawItemsCount={violationsData?.items.length ?? 0}
            loadingV={loadingV}
            onRetryViolations={() => void refetchViolations()}
            filteredList={filteredList}
            pageItems={pageItems}
            safePage={safePage}
            pageCount={pageCount}
            onPageChange={setPage}
            cameraName={cameraName}
            now={now}
            canOperate={canOperate}
            resolvingViolationId={resolvingViolationId}
            onOpenFrame={openFrame}
            onResolveViolation={resolveViolation}
          />
        )}
      </AppShell>

      <Dialog
        open={editOpen}
        onOpenChange={(open) => {
          if (!open) {
            setEditOpen(false)
            setEditingCamera(null)
          }
        }}
      >
        <DialogContent className="max-w-lg rounded-2xl border-border bg-card">
          <DialogHeader>
            <DialogTitle className="font-bold text-foreground">تعديل الكاميرا</DialogTitle>
            <DialogDescription>يمكنك تعديل الاسم والرابط والفئات المفعّلة.</DialogDescription>
          </DialogHeader>
          {editingCamera && (
            <AddCameraForm
              key={editingCamera.id}
              mode="edit"
              camera={editingCamera}
              onSuccess={() => {
                setEditOpen(false)
                setEditingCamera(null)
                notify("success", "تم تحديث الكاميرا بنجاح")
              }}
            />
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteOpen}
        title="تأكيد حذف الكاميرا"
        description={
          deleteTarget ? `هل أنت متأكد أنك تريد حذف «${deleteTarget.name}»؟` : undefined
        }
        confirmLabel="حذف"
        cancelLabel="إلغاء"
        tone="destructive"
        pending={deleteMut.isPending}
        onCancel={() => {
          if (deleteMut.isPending) return
          setDeleteOpen(false)
          setDeleteTarget(null)
        }}
        onConfirm={confirmDelete}
      />

      <Dialog
        open={frameUrl !== null}
        onOpenChange={(open) => {
          if (!open) setFrameUrl(null)
        }}
      >
        <DialogContent className="max-w-5xl overflow-hidden rounded-2xl border-border bg-background p-0 shadow-2xl">
          <DialogHeader className="border-b border-border bg-card/90 p-4 text-start">
            <DialogTitle className="text-sm font-bold text-foreground">
              معاينة الدليل المرئي
            </DialogTitle>
            <DialogDescription className="text-xs">
              اللقطة التي رصد فيها النظام المخالفة
            </DialogDescription>
          </DialogHeader>
          <div className="flex min-h-[400px] items-center justify-center bg-black p-6">
            {frameUrl && (
              <img
                src={frameUrl}
                className="max-h-[75vh] max-w-full rounded-xl border border-white/10 shadow-[0_0_60px_rgba(0,0,0,0.6)]"
                alt="لقطة المخالفة"
              />
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </>
  )
}
