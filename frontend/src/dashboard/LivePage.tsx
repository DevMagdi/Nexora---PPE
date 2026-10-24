import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Cctv, Loader2, Play, RefreshCw, ShieldAlert, Square } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Empty, InlineError } from "@/components/Feedback"
import { CONNECTION_LABEL, sourceIsBusy } from "@/cameras/sources"
import useLiveCamera from "@/hooks/useLiveCamera"
import { getMjpegStreamUrl, startCamera, stopCamera } from "@/lib/api"
import { RULE_LABEL, num } from "@/lib/formatters"
import type { Camera, Site } from "@/types"

export default function LivePage({
  cameras,
  sites,
  selectedId,
  onSelect,
  canOperate,
  refresh,
}: {
  cameras: Camera[]
  sites: Site[]
  selectedId: number | null
  onSelect: (id: number) => void
  canOperate: boolean
  refresh: () => Promise<void>
}) {
  const [attempt, setAttempt] = useState(0)
  const [imageError, setImageError] = useState(false)
  const camera = cameras.find((item) => item.id === selectedId) ?? cameras[0]
  const live = useLiveCamera(camera?.id, camera?.is_running ?? false, attempt)
  const toggle = useMutation({
    mutationFn: () => (sourceIsBusy(camera) ? stopCamera(camera.id) : startCamera(camera.id)),
    onSuccess: async () => {
      setImageError(false)
      setAttempt((value) => value + 1)
      await refresh()
    },
    onError: async () => {
      await refresh()
    },
  })
  const choose = (id: number) => {
    setImageError(false)
    onSelect(id)
  }
  if (!camera)
    return (
      <div className="panel">
        <Empty
          icon={<Cctv />}
          title="لا توجد مصادر للمراقبة"
          description="أضف كاميرا RTSP أو ارفع فيديو لبدء رصد معدات الوقاية الصناعية."
        />
      </div>
    )
  const negatives = [
    live.counts?.no_hardhat,
    live.counts?.no_vest,
    live.counts?.no_gloves,
    live.counts?.no_boot,
    live.counts?.no_goggles,
  ]
  return (
    <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_288px]">
      <section className="panel min-w-0 overflow-hidden">
        <div className="panel-header">
          <div>
            <h2>{camera.name}</h2>
            <p>{sites.find((site) => site.id === camera.site_id)?.name ?? "موقع غير معيّن"}</p>
          </div>
          <span className={`badge ${live.status === "مباشر" ? "badge-success" : ""}`}>
            <span className="status-dot" />
            {camera.is_running
              ? live.status
              : (CONNECTION_LABEL[camera.connection_status] ?? "متوقفة")}
          </span>
        </div>
        {camera.last_error && (
          <p className="notice notice-error mx-5 mt-5" role="alert">
            {camera.last_error}
          </p>
        )}
        <div className="live-stage">
          <div className="live-canvas">
            {camera.is_running && !imageError ? (
              <>
                <img
                  key={`${camera.id}-${attempt}`}
                  src={getMjpegStreamUrl(camera.id)}
                  alt={`بث مباشر من ${camera.name}`}
                  onError={() => setImageError(true)}
                />
                <span className="badge absolute start-4 top-4 latin">LIVE / CAM-{camera.id}</span>
              </>
            ) : (
              <div className="empty-state">
                <span className="empty-state-icon" aria-hidden="true">
                  <Cctv />
                </span>
                <h3>
                  {imageError
                    ? "تعذّر عرض البث"
                    : camera.connection_status === "completed"
                      ? "اكتملت معالجة الفيديو"
                      : camera.connection_status === "error"
                        ? "فشل اتصال المصدر"
                        : sourceIsBusy(camera)
                          ? "إعادة اتصال بالمصدر"
                          : "مصدر المراقبة متوقف"}
                </h3>
                <p>
                  {imageError
                    ? "تحقق من الاتصال وصلاحية جلسة البث، ثم أعد المحاولة."
                    : "شغّل المصدر لبدء الاستدلال. لا يتم عرض إطارات أو عدادات تجريبية."}
                </p>
                {imageError ? (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setImageError(false)
                      setAttempt((value) => value + 1)
                    }}
                  >
                    <RefreshCw />
                    إعادة الاتصال
                  </Button>
                ) : (
                  canOperate && (
                    <Button disabled={toggle.isPending} onClick={() => toggle.mutate()}>
                      {toggle.isPending ? <Loader2 /> : <Play />}
                      {sourceIsBusy(camera) ? "إيقاف المحاولة" : "تشغيل المصدر"}
                    </Button>
                  )
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
          <span className="text-[11px] text-muted-foreground">
            مراقبة صناعية · معدات الوقاية المفعّلة فقط
          </span>
          {canOperate && (
            <Button
              variant="outline"
              size="sm"
              disabled={toggle.isPending}
              onClick={() => toggle.mutate()}
            >
              {toggle.isPending ? <Loader2 /> : sourceIsBusy(camera) ? <Square /> : <Play />}
              {sourceIsBusy(camera) ? "إيقاف البث" : "بدء البث"}
            </Button>
          )}
        </div>
        {toggle.error && (
          <div className="p-4 pt-0">
            <InlineError error={toggle.error} />
          </div>
        )}
        <div className="quiet-strip">
          {[
            { label: "رصد أشخاص", value: live.counts?.person },
            { label: "رصد خوذات", value: live.counts?.hardhat },
            { label: "رصد سترات", value: live.counts?.vest },
          ].map((item) => (
            <div key={item.label}>
              <div className="quiet-strip-value">{num(item.value)}</div>
              <p className="quiet-strip-label">{item.label}</p>
            </div>
          ))}
        </div>
      </section>
      <div className="space-y-6">
        <section className="panel p-6">
          <label htmlFor="live-camera" className="field-label">
            مصدر المراقبة
          </label>
          <select
            id="live-camera"
            className="field"
            value={camera.id}
            onChange={(e) => choose(Number(e.target.value))}
          >
            {cameras.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
                {` · ${CONNECTION_LABEL[item.connection_status] ?? "متوقفة"}`}
              </option>
            ))}
          </select>
          <p className="mt-4 text-[10px] text-muted-foreground">قواعد المصدر</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {camera.enabled_classes.map((rule) => (
              <span className="badge" key={rule}>
                {RULE_LABEL[rule]}
              </span>
            ))}
          </div>
        </section>
        <section className="panel p-6">
          <div className="mb-2 flex items-center gap-2">
            <ShieldAlert className="size-4 shrink-0 text-muted-foreground" strokeWidth={1.5} />
            <h2 className="text-sm font-medium">المخالفات في الإطار الحالي</h2>
          </div>
          <div>
            {["بدون خوذة", "بدون سترة", "بدون قفازات", "بدون حذاء أمان", "بدون نظارات"].map(
              (label, index) => (
                <div key={label} className="stat-row">
                  <span className="text-muted-foreground">{label}</span>
                  <span
                    className={`latin ${negatives[index] ? "text-destructive" : "text-foreground"}`}
                  >
                    {num(negatives[index])}
                  </span>
                </div>
              ),
            )}
          </div>
          <p className="mt-5 border-t border-border pt-4 text-[10px] leading-[1.9] text-muted-foreground">
            العدادات لحظية لكل إطار، وليست هويات أو أعداداً فريدة للعاملين. التنبيه يحتاج دليلاً
            مستمراً خلال مدة الثبات.
          </p>
        </section>
      </div>
    </div>
  )
}
