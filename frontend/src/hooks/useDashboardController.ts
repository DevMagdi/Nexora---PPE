import { useCallback, useEffect, useMemo, useState } from "react"
import { useCameras, useHealth, useMe, usePPEClassesMeta, useResolveViolation, useStartCamera, useStopCamera, useViolations } from "@/hooks/useNexora"
import { downloadViolationsCsv, logout, refreshMediaSession, resolveFrameUrl } from "@/lib/api"
import { cameraProfile, compareViolationsByNewest, computeCompliance, DAY, getRangeLabel, HOUR, iso, isCoreType, LOCALE, MAX_GRID_PREVIEWS, parseTs, VIOLATIONS_FETCH_LIMIT, violationLabel } from "@/lib/domain"
import { getErrorMessage } from "@/lib/utils"
import { useLiveCounts } from "@/hooks/useLiveCounts"
import { useTheme } from "@/hooks/useTheme"
import type { Camera, Violation } from "@/types"
import type { LiveStatus, RangeKey, TabKey, ToastState } from "@/types/app"

export function useDashboardController() {
  const [dark, setDark] = useTheme()
  const { data: user } = useMe()
  const { data: health, isLoading: healthLoading, isError: healthError, refetch: refetchHealth } = useHealth()
  const { data: cameras, isLoading: camerasLoading, isError: camerasError, refetch: refetchCameras } = useCameras()
  const { data: ppeConstruction } = usePPEClassesMeta("construction")
  const { data: ppeMedical } = usePPEClassesMeta("medical")

  const startMutation = useStartCamera()
  const stopMutation = useStopCamera()
  const resolveMutation = useResolveViolation()

  const [tab, setTab] = useState<TabKey>("overview")
  const [range, setRange] = useState<RangeKey>("24h")
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null)
  const [liveGeneration, setLiveGeneration] = useState(0)
  const [streamActiveFor, setStreamActiveFor] = useState<string | null>(null)
  const [frameUrl, setFrameUrl] = useState<string | null>(null)
  const [typeInput, setTypeInput] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [cameraFilter, setCameraFilter] = useState<number | "all">("all")
  const [exporting, setExporting] = useState(false)
  const [seenByRange, setSeenByRange] = useState<Partial<Record<RangeKey, number>>>({})
  const [toast, setToast] = useState<ToastState | null>(null)
  const [now, setNow] = useState(() => Date.now())

  const userId = user?.id
  const canOperate = user?.role === "admin" || user?.role === "operator"

  useEffect(() => {
    if (!userId || user?.must_change_password) return
    const renew = () => void refreshMediaSession().catch(() => undefined)
    renew()
    const timer = window.setInterval(renew, 5 * 60 * 1000)
    return () => window.clearInterval(timer)
  }, [userId, user?.must_change_password])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const fromTo = useMemo(() => {
    const duration = range === "24h" ? DAY : 7 * DAY
    return { from: new Date(now - duration), to: new Date(now) }
  }, [range, now])
  const rangeLabel = getRangeLabel(range)
  const changeRange = useCallback((next: RangeKey) => {
    if (range === next) return
    setRange(next)
  }, [range])

  const notify = useCallback((tone: ToastState["tone"], text: string) => setToast({ id: Date.now(), tone, text }), [])
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 3500)
    return () => window.clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    const timer = window.setTimeout(() => setTypeFilter(typeInput.trim()), 350)
    return () => window.clearTimeout(timer)
  }, [typeInput])

  const ppeLabels = useMemo(() => {
    const labels = new Map<string, string>()
    for (const item of [...(ppeConstruction?.items ?? []), ...(ppeMedical?.items ?? [])]) labels.set(item.key, item.label_ar)
    return labels
  }, [ppeConstruction, ppeMedical])

  const cameraList = useMemo(() => cameras ?? [], [cameras])
  const cameraName = useCallback((id: number) => cameraList.find((camera) => camera.id === id)?.name ?? `كاميرا #${id}`, [cameraList])
  const totalCameras = cameraList.length
  const runningCameras = useMemo(() => cameraList.filter((camera) => camera.is_running), [cameraList])
  const runningCount = runningCameras.length
  const selectedCamera = useMemo(() => {
    if (cameraList.length === 0) return null
    if (selectedCameraId !== null) {
      const found = cameraList.find((camera) => camera.id === selectedCameraId)
      if (found) return found
    }
    return cameraList.find((camera) => camera.is_running) ?? cameraList[0]
  }, [cameraList, selectedCameraId])

  const startPendingId = startMutation.isPending ? startMutation.variables : undefined
  const stopPendingId = stopMutation.isPending ? stopMutation.variables : undefined
  const togglingCameraId = startPendingId ?? stopPendingId ?? null
  const resolvingViolationId = resolveMutation.isPending ? resolveMutation.variables : null

  const toggleCamera = useCallback((camera: Camera) => {
    if (selectedCamera?.id === camera.id) {
      setLiveGeneration((generation) => generation + 1)
      setStreamActiveFor(null)
    }
    const mutation = camera.is_running ? stopMutation : startMutation
    const action = camera.is_running ? "إيقاف" : "تشغيل"
    mutation.mutate(camera.id, {
      onSuccess: () => notify("success", `تم ${action} «${camera.name}» بنجاح`),
      onError: (error) => notify("error", `${getErrorMessage(error, `تعذّر ${action} «${camera.name}»`)} · ${camera.name}`),
    })
  }, [startMutation, stopMutation, notify, selectedCamera?.id])

  const selectCamera = useCallback((id: number) => {
    setSelectedCameraId(id)
    setTab("live")
    setLiveGeneration((generation) => generation + 1)
    setStreamActiveFor(null)
  }, [])

  const onCameraDeleted = useCallback((camera: Camera) => {
    if (selectedCameraId === camera.id) setSelectedCameraId(null)
  }, [selectedCameraId])

  const resolveViolation = useCallback((violation: Violation) => {
    resolveMutation.mutate(violation.id, {
      onSuccess: () => notify("success", "تم تعليم المخالفة كمعالجة"),
      onError: (error) => notify("error", getErrorMessage(error, "تعذّر تعليم المخالفة كمعالجة")),
    })
  }, [resolveMutation, notify])

  const openFrame = useCallback((url?: string | null) => {
    if (!url) return
    const resolved = resolveFrameUrl(url)
    if (resolved) setFrameUrl(resolved)
  }, [])
  const handleLogout = useCallback(() => { void logout() }, [])
  const baseParams = useMemo(() => ({ page_size: VIOLATIONS_FETCH_LIMIT, from: iso(fromTo.from), to: iso(fromTo.to) }), [fromTo])
  const tableParams = useMemo(() => ({
    ...baseParams,
    ...(cameraFilter !== "all" ? { camera_id: cameraFilter } : {}),
    ...(typeFilter ? { violation_type: typeFilter } : {}),
  }), [baseParams, cameraFilter, typeFilter])

  const { data: overviewData, isLoading: overviewLoading, isError: overviewError, refetch: refetchOverview } = useViolations(baseParams)
  const { data: violationsData, isLoading: violationsLoading, isError: violationsError, refetch: refetchViolations } = useViolations(tableParams)

  const overviewList = useMemo(() => Array.from(overviewData?.items ?? []).sort(compareViolationsByNewest), [overviewData])
  const onMarkSeen = useCallback(() => setSeenByRange((previous) => ({ ...previous, [range]: overviewData?.items.length ?? 0 })), [range, overviewData?.items.length])
  const coreCount = useMemo(() => overviewList.filter((violation) => isCoreType(violation.violation_type)).length, [overviewList])
  const overviewCapped = (overviewData?.total ?? 0) > (overviewData?.items.length ?? 0)
  const openViolations = useMemo(() => overviewList.filter((violation) => !violation.is_resolved).length, [overviewList])

  const knownTypes = useMemo(() => {
    const types = new Set<string>()
    for (const violation of overviewList) types.add(violation.violation_type)
    for (const violation of violationsData?.items ?? []) types.add(violation.violation_type)
    return [...types].sort()
  }, [overviewList, violationsData])

  const onExport = useCallback(async () => {
    setExporting(true)
    try {
      await downloadViolationsCsv({ camera_id: cameraFilter === "all" ? undefined : cameraFilter, from: iso(fromTo.from), to: iso(fromTo.to), violation_type: typeFilter || undefined })
      notify("success", "تم تنزيل ملف المخالفات")
    } catch (error) {
      notify("error", getErrorMessage(error, "تعذّر تصدير المخالفات"))
    } finally {
      setExporting(false)
    }
  }, [cameraFilter, fromTo, typeFilter, notify])

  const series = useMemo(() => {
    const buckets = range === "24h" ? 24 : 7
    const size = range === "24h" ? HOUR : DAY
    const start = fromTo.from.getTime()
    const points = Array.from({ length: buckets }, (_, index) => {
      const date = new Date(start + index * size)
      const label = range === "24h"
        ? date.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", hour12: false })
        : date.toLocaleDateString(LOCALE, { weekday: "short" })
      return { label, count: 0 }
    })
    for (const violation of overviewList) {
      const index = Math.floor((parseTs(violation.timestamp).getTime() - start) / size)
      if (index >= 0 && index < buckets) points[index].count += 1
    }
    return points
  }, [overviewList, fromTo, range])

  const pieData = useMemo(() => {
    const counts = new Map<string, number>()
    for (const violation of overviewList) counts.set(violation.violation_type, (counts.get(violation.violation_type) ?? 0) + 1)
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([type, value]) => ({ name: violationLabel(type, ppeLabels), value }))
  }, [overviewList, ppeLabels])

  const liveConnection = useLiveCounts(selectedCamera?.id, Boolean(selectedCamera?.is_running), liveGeneration)
  const streamKey = `${selectedCamera?.id ?? "none"}-${Boolean(selectedCamera?.is_running)}-${liveGeneration}`
  const streamLive = streamActiveFor === streamKey
  const handleStreamReady = useCallback(() => setStreamActiveFor(streamKey), [streamKey])
  const handleStreamLost = useCallback(() => setStreamActiveFor(null), [])

  const activeProfile = selectedCamera ? cameraProfile(selectedCamera) : user?.sector === "medical" ? "medical" : "construction"
  const isMedicalView = activeProfile === "medical"
  const activeCounts = selectedCamera?.is_running ? liveConnection.counts : {}
  const activeLiveStatus: LiveStatus = !selectedCamera?.is_running
    ? "idle"
    : streamLive
      ? "open"
      : liveConnection.status === "open"
        ? "connecting"
        : liveConnection.status
  const compliance = selectedCamera?.is_running ? computeCompliance(activeProfile, activeCounts) : undefined
  const medicalNegatives = selectedCamera?.is_running && isMedicalView
    ? (activeCounts.no_mask ?? 0) + (activeCounts.no_gloves ?? 0) + (activeCounts.no_goggles ?? 0) + (activeCounts.no_cap ?? 0)
    : undefined
  const cameraPending = selectedCamera !== null && togglingCameraId === selectedCamera.id

  const effectiveSeenCount = seenByRange[range] ?? (overviewData ? overviewData.items.length : null)
  const unseen = effectiveSeenCount === null ? 0 : Math.max(0, overviewList.length - effectiveSeenCount)
  const orderedCameras = useMemo(() => [...cameraList].sort((a, b) => Number(b.is_running) - Number(a.is_running)), [cameraList])
  const previewAllowed = useMemo(() => {
    const ids = new Set<number>()
    for (const camera of orderedCameras) if (camera.is_running && ids.size < MAX_GRID_PREVIEWS) ids.add(camera.id)
    return ids
  }, [orderedCameras])

  const alertsByCamera = useMemo(() => {
    const alerts = new Map<number, number>()
    for (const violation of overviewList) {
      const age = now - parseTs(violation.timestamp).getTime()
      if (isCoreType(violation.violation_type) && age >= 0 && age < HOUR) alerts.set(violation.camera_id, (alerts.get(violation.camera_id) ?? 0) + 1)
    }
    return alerts
  }, [overviewList, now])
  const hourAlerts = useMemo(() => [...alertsByCamera.values()].reduce((sum, count) => sum + count, 0), [alertsByCamera])
  const headline = isMedicalView
    ? medicalNegatives === undefined ? "شغّل كاميرا لبدء الرصد الطبي" : medicalNegatives === 0 ? "لا توجد مخالفات ظاهرة في الكادر" : "توجد مخالفات معدات طبية في الكادر"
    : compliance === undefined ? "شغّل كاميرا لبدء قياس الالتزام" : compliance >= 90 ? "الموقع ملتزم بمعدات الوقاية" : compliance >= 70 ? "الالتزام يحتاج متابعة" : "الالتزام منخفض، تدخّل الآن"

  const refetch = (query: () => Promise<unknown>) => () => { void query() }

  return {
    dark,
    setDark,
    user,
    health,
    healthLoading,
    healthError,
    refetchHealth: refetch(refetchHealth),
    cameraList,
    cameraName,
    camerasLoading,
    camerasError,
    refetchCameras: refetch(refetchCameras),
    totalCameras,
    runningCount,
    canOperate,
    ppeLabels,
    tab,
    setTab,
    range,
    changeRange,
    rangeLabel,
    selectedCamera,
    selectCamera,
    onCameraDeleted,
    toggleCamera,
    togglingCameraId,
    cameraPending,
    resolvingViolationId,
    resolveViolation,
    violationsData,
    violationsLoading,
    violationsError,
    refetchViolations: refetch(refetchViolations),
    cameraFilter,
    setCameraFilter,
    typeInput,
    typeFilter,
    setTypeInput,
    knownTypes,
    exporting,
    onExport,
    overviewData,
    overviewList,
    overviewLoading,
    overviewError,
    refetchOverview: refetch(refetchOverview),
    coreCount,
    overviewCapped,
    openViolations,
    series,
    pieData,
    activeCounts,
    activeLiveStatus,
    compliance,
    medicalNegatives,
    isMedicalView,
    headline,
    hourAlerts,
    alertsByCamera,
    orderedCameras,
    previewAllowed,
    unseen,
    onMarkSeen,
    now,
    frameUrl,
    openFrame,
    closeFrame: () => setFrameUrl(null),
    toast,
    clearToast: () => setToast(null),
    notify,
    handleLogout,
    handleStreamReady,
    handleStreamLost,
  }
}
