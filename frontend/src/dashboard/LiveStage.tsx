import { useState } from "react"
import { AlertTriangle, Camera as CameraIcon, Loader2, MonitorPlay, Play, RefreshCw, Square, WifiOff } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getMjpegStreamUrl } from "@/lib/api"
import { PROFILE_LABEL, withParams, cameraProfile } from "@/lib/domain"
import type { Camera } from "@/types"
import type { LiveStatus } from "@/types/app"

type Props = {
  camera: Camera | null
  status: LiveStatus
  pending: boolean
  canOperate: boolean
  onStart: () => void
  onStop: () => void
  onGoCameras: () => void
  onStreamReady: () => void
  onStreamLost: () => void
}

const LIVE_STATUS_LABEL: Record<LiveStatus, string> = {
  idle: "",
  connecting: "جارٍ الاتصال...",
  reconnecting: "إعادة الاتصال...",
  open: "مباشر",
}

export function LiveStage({ camera, status, pending, canOperate, onStart, onStop, onGoCameras, onStreamReady, onStreamLost }: Props) {
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const currentStreamKey = `${camera?.id ?? "none"}-${camera?.is_running ?? false}-${nonce}`
  const streamError = errorKey === currentStreamKey

  const retry = () => {
    setErrorKey(null)
    setNonce((current) => current + 1)
  }

  if (!camera) {
    return (
      <div className="flex min-h-full w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-6 text-center sm:p-10">
        <div className="mb-5 flex size-16 items-center justify-center rounded-2xl bg-primary-light text-primary">
          <MonitorPlay className="size-8" />
        </div>
        <h3 className="text-lg font-bold sm:text-xl">اختر كاميرا لبدء المراقبة</h3>
        <p className="mb-5 mt-2 max-w-sm text-sm leading-6 text-muted-foreground">اختر أحد المصادر من القائمة لعرض البث المباشر والتحليل الذكي.</p>
        <Button type="button" variant="outline" onClick={onGoCameras} className="min-h-11 gap-2 rounded-xl">
          <CameraIcon className="size-4" /> إدارة الكاميرات
        </Button>
      </div>
    )
  }

  if (!camera.is_running) {
    return (
      <div className="flex min-h-full w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-6 text-center sm:p-10">
        <div className="mb-5 flex size-16 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <WifiOff className="size-8" />
        </div>
        <h3 className="text-lg font-bold sm:text-xl">البث متوقف حاليًا</h3>
        <p className="mb-5 mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
          {canOperate ? `«${camera.name}» لا تعمل الآن. يمكنك تشغيل البث والتحليل اللحظي.` : `«${camera.name}» لا تعمل الآن. اطلب من مدير النظام تشغيلها.`}
        </p>
        {canOperate && (
          <Button type="button" onClick={onStart} disabled={pending} className="min-h-11 gap-2 rounded-xl">
            {pending ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4 fill-current" />}
            {pending ? "جارٍ التشغيل..." : "تشغيل البث الآن"}
          </Button>
        )}
      </div>
    )
  }

  const streamSrc = withParams(getMjpegStreamUrl(camera.id), nonce ? { r: String(nonce) } : {})
  const isLive = status === "open"

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-[#070b0b]">
      {streamError ? (
        <div role="alert" className="relative z-10 flex h-full w-full flex-col items-center justify-center p-6 text-center sm:p-10">
          <div className="mb-4 flex size-14 items-center justify-center rounded-2xl bg-warning/10 text-warning">
            <AlertTriangle className="size-7" />
          </div>
          <h3 className="text-lg font-bold text-white">تعذّر الاتصال بالبث</h3>
          <p className="mb-5 mt-2 max-w-sm text-sm leading-6 text-white/65">الكاميرا تعمل لكن تدفق الفيديو لم يصل. تحقق من المصدر أو الشبكة ثم أعد المحاولة.</p>
          <Button type="button" variant="outline" onClick={retry} className="min-h-11 gap-2 rounded-xl border-white/15 bg-white/10 text-white hover:bg-white/15">
            <RefreshCw className="size-4" /> إعادة المحاولة
          </Button>
        </div>
      ) : (
        <img
          key={`${camera.id}-${nonce}`}
          src={streamSrc}
          onLoad={onStreamReady}
          onError={() => {
            setErrorKey(currentStreamKey)
            onStreamLost()
          }}
          className="absolute inset-0 z-0 h-full w-full object-contain"
          alt={`البث المباشر من ${camera.name}`}
          draggable={false}
        />
      )}

      {!streamError && <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-[5] shadow-[inset_0_0_100px_rgba(0,0,0,0.35)]" />}

      <div className="absolute inset-x-0 top-0 z-10 bg-gradient-to-b from-black/80 via-black/25 to-transparent p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-bold text-white drop-shadow sm:text-lg">{camera.name}</h2>
            <p className="mt-1 text-xs text-white/65">#{camera.id} · {PROFILE_LABEL[cameraProfile(camera)]} · {camera.source_type}</p>
          </div>
          <Badge className={`shrink-0 border-none px-3 py-1 text-xs font-bold text-white ${isLive ? "bg-red-600/95" : "bg-amber-700/95"}`}>
            <span className={`me-1.5 size-1.5 rounded-full ${isLive ? "bg-white animate-pulse" : "bg-white/70"}`} />
            {isLive ? "مباشر" : LIVE_STATUS_LABEL[status] || "جارٍ تجهيز البث"}
          </Badge>
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-0 z-10 flex items-end justify-between gap-3 bg-gradient-to-t from-black/80 via-black/20 to-transparent p-4 pt-12 sm:p-5 sm:pt-14">
        <p className="text-xs font-medium text-white/75">{isLive ? "التحليل اللحظي متصل" : "جارٍ استعادة اتصال التحليل"}</p>
        {canOperate && (
          <Button type="button" size="sm" variant="destructive" onClick={onStop} disabled={pending} className="min-h-11 gap-2 rounded-xl px-4">
            {pending ? <Loader2 className="size-4 animate-spin" /> : <Square className="size-3.5 fill-current" />}
            إيقاف البث
          </Button>
        )}
      </div>
    </div>
  )
}
