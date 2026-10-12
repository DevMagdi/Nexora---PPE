import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, HardHat, Loader2, ShieldCheck, Stethoscope, Video } from "lucide-react"
import PpeClassPicker from "@/components/PpeClassPicker"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCreateCamera, useMe, usePPEClassesMeta, useUpdateCamera } from "@/hooks/useNexora"
import { getErrorMessage } from "@/lib/utils"
import SkeletonBlock from "@/shared/SkeletonBlock"
import type { Camera, CameraProfile, CameraSourceType } from "@/types"

const SOURCE_TYPE_LABELS: Record<CameraSourceType, string> = {
  webcam: "كاميرا ويب محلية (Webcam)",
  rtsp: "بث شبكي مباشر (RTSP)",
  file: "ملف فيديو مسجّل (File)",
}

type Props = {
  mode?: "create" | "edit"
  camera?: Camera
  onSuccess?: () => void
}

export default function AddCameraForm({ mode = "create", camera, onSuccess }: Props) {
  const createMut = useCreateCamera()
  const updateMut = useUpdateCamera()
  const { data: me } = useMe()

  const isEdit = mode === "edit" && camera !== undefined
  const pending = isEdit ? updateMut.isPending : createMut.isPending

  const [name, setName] = useState(camera?.name ?? "")
  const [sourceType, setSourceType] = useState<CameraSourceType>(camera?.source_type ?? "rtsp")
  const [sourceUri, setSourceUri] = useState(mode === "edit" ? "" : camera?.source_uri ?? "")
  const [enabled, setEnabled] = useState<string[]>(camera?.enabled_classes ?? [])
  const [error, setError] = useState<string | null>(null)

  const [profile, setProfile] = useState<CameraProfile>(
    (camera?.profile as CameraProfile) ?? "construction",
  )

  const effectiveProfile: CameraProfile = useMemo(() => {
    if (isEdit && camera?.profile) return camera.profile
    if (me?.sector && me.sector !== "both") return me.sector
    return profile
  }, [isEdit, camera?.profile, me?.sector, profile])

  const {
    data: ppeMeta,
    isLoading: ppeLoading,
    isError: ppeError,
  } = usePPEClassesMeta(effectiveProfile)

  const defaultEnabled = useMemo<string[]>(
    () =>
      ppeMeta?.default_enabled?.length
        ? ppeMeta.default_enabled
        : effectiveProfile === "medical"
          ? ["mask", "gloves", "cap"]
          : ["helmet", "vest"],
    [ppeMeta, effectiveProfile],
  )

  const allowedKeys = useMemo<Set<string>>(
    () => new Set((ppeMeta?.allowed ?? defaultEnabled).map(String)),
    [ppeMeta, defaultEnabled],
  )

  const placeholder = useMemo(() => {
    if (isEdit) return "اتركه فارغًا للإبقاء على المصدر الحالي؛ أدخل مصدرًا جديدًا عند التغيير"
    if (sourceType === "webcam") return "Webcam index مثل: 0 أو 1"
    if (sourceType === "rtsp") return "rtsp://user:pass@ip:554/..."
    return "مسار ملف فيديو داخل مجلد الفيديو المسموح"
  }, [isEdit, sourceType])

  useEffect(() => {
    if (isEdit) return
    if (enabled.length === 0) setEnabled(defaultEnabled)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, defaultEnabled])

  useEffect(() => {
    if (isEdit) return
    if (sourceType === "webcam" && !/^\d+$/.test(sourceUri)) setSourceUri("0")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceType])

  useEffect(() => {
    if (isEdit) return
    setEnabled(defaultEnabled)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveProfile])

  function sanitizeEnabled(values: string[]) {
    const cleaned = (values ?? []).map(String).filter((k) => allowedKeys.has(k))
    return Array.from(new Set(cleaned))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (sourceType === "webcam" && sourceUri.trim() && !/^\d+$/.test(sourceUri.trim())) {
      setError("بالنسبة للـ Webcam لازم تكتب رقم index مثل 0 أو 1.")
      return
    }

    const enabledClean = sanitizeEnabled(enabled)
    const finalEnabled = enabledClean.length ? enabledClean : defaultEnabled

    try {
      if (isEdit && camera) {
        await updateMut.mutateAsync({
          id: camera.id,
          payload: {
            name: name.trim(),
            ...(sourceUri.trim() ? { source_uri: sourceUri.trim() } : {}),
            enabled_classes: finalEnabled,
          },
        })
      } else {
        await createMut.mutateAsync({
          name: name.trim(),
          source_type: sourceType,
          source_uri: sourceUri.trim(),
          profile: effectiveProfile,
          enabled_classes: finalEnabled,
        })
        setName("")
        setSourceUri(sourceType === "webcam" ? "0" : "")
        setEnabled(defaultEnabled)
      }

      onSuccess?.()
    } catch (err) {
      setError(getErrorMessage(err, isEdit ? "فشل تحديث الكاميرا" : "فشل إضافة الكاميرا"))
    }
  }

  return (
    <Card className="border-0 shadow-none">
      <CardContent className="p-0">
        <form onSubmit={submit} className="space-y-5">
          {/* ─── Step 1: Source & Sector Configuration ─── */}
          <div className="surface-flat space-y-3.5 p-4">
            <div className="flex items-center gap-2 text-xs font-bold text-primary">
              <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[11px] text-primary-foreground">
                1
              </span>
              <Video className="size-3.5" />
              <span>إعدادات المصدر والقطاع</span>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="cam-name" className="text-xs font-bold text-foreground">
                اسم الكاميرا / موقع الرصد
              </Label>
              <Input
                id="cam-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="مثال: البوابة الشمالية - منطقة الرافعات"
                required
                className="h-10 rounded-xl bg-card"
              />
            </div>

            {!isEdit && me?.sector === "both" && (
              <div className="space-y-1.5">
                <Label className="text-xs font-bold text-foreground">القطاع التشغيلي</Label>
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => setProfile("construction")}
                    className={`flex min-h-11 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold transition-all cursor-pointer ${
                      effectiveProfile === "construction"
                        ? "border-primary/40 bg-primary-light text-primary"
                        : "border-border bg-card text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <HardHat className="size-4 shrink-0" />
                    <span>الإنشاءات والمصانع</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setProfile("medical")}
                    className={`flex min-h-11 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold transition-all cursor-pointer ${
                      effectiveProfile === "medical"
                        ? "border-primary/40 bg-primary-light text-primary"
                        : "border-border bg-card text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Stethoscope className="size-4 shrink-0" />
                    <span>القطاع الطبي</span>
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <Label className="text-xs font-bold text-foreground">نوع المصدر</Label>
              {isEdit ? (
                <div className="flex h-10 items-center rounded-xl border border-input bg-card/60 px-3 text-xs font-medium text-muted-foreground">
                  نوع المصدر: {SOURCE_TYPE_LABELS[sourceType]} (غير قابل للتعديل)
                </div>
              ) : (
                <Select
                  value={sourceType}
                  onValueChange={(v) => setSourceType(v as CameraSourceType)}
                >
                  <SelectTrigger className="h-10 w-full rounded-xl bg-card">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="webcam">{SOURCE_TYPE_LABELS.webcam}</SelectItem>
                    <SelectItem value="rtsp">{SOURCE_TYPE_LABELS.rtsp}</SelectItem>
                    <SelectItem value="file">{SOURCE_TYPE_LABELS.file}</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="cam-uri" className="text-xs font-bold text-foreground">
                رابط أو معرّف المصدر
              </Label>
              <Input
                id="cam-uri"
                dir="ltr"
                type={sourceType === "webcam" ? "number" : "text"}
                value={sourceUri}
                onChange={(e) => setSourceUri(e.target.value)}
                placeholder={placeholder}
                required={!isEdit}
                className="h-10 rounded-xl bg-card font-mono text-xs"
              />
            </div>
          </div>

          {/* ─── Step 2: PPE Detection Rules ─── */}
          <div className="surface-flat space-y-3 p-4">
            <div className="flex items-center gap-2 text-xs font-bold text-primary">
              <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[11px] text-primary-foreground">
                2
              </span>
              <ShieldCheck className="size-3.5" />
              <span>قواعد الرصد ومعدات الوقاية المطلوب مراقبتها</span>
            </div>

            {ppeLoading ? (
              <div className="grid grid-cols-2 gap-2">
                {Array.from({ length: 4 }, (_, i) => (
                  <SkeletonBlock key={i} className="h-11 rounded-xl" />
                ))}
              </div>
            ) : ppeError || !ppeMeta ? (
              <div className="text-xs font-semibold text-destructive">
                تعذّر تحميل قائمة معدات الوقاية
              </div>
            ) : (
              <PpeClassPicker items={ppeMeta.items} value={enabled} onChange={setEnabled} />
            )}
          </div>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive-light p-3 text-xs font-semibold text-destructive-foreground"
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
              <span>{error}</span>
            </div>
          )}

          <Button
            disabled={pending}
            type="submit"
            className="btn-cta h-11 w-full rounded-xl text-sm font-bold"
          >
            {pending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                جارٍ الحفظ...
              </>
            ) : isEdit ? (
              "حفظ التعديلات"
            ) : (
              "ربط وإضافة الكاميرا"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
