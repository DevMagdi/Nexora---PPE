import { useEffect, useMemo, useState } from "react"
import { Camera, ShieldCheck } from "lucide-react"
import PpeClassPicker from "@/components/PpeClassPicker"
import { useCreateCamera, useMe, usePPEClassesMeta, useUpdateCamera } from "@/hooks/useNexora"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getErrorMessage } from "@/lib/utils"
import type { Camera as CameraModel, CameraSourceType, CameraProfile } from "@/types"

const SOURCE_TYPE_LABELS: Record<CameraSourceType, string> = {
  webcam: "كاميرا ويب (Webcam)",
  rtsp: "بث شبكي (RTSP)",
  file: "ملف فيديو",
}

type Props = {
  mode?: "create" | "edit"
  camera?: CameraModel
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
  const [profile, setProfile] = useState<CameraProfile>((camera?.profile as CameraProfile) ?? "construction")

  const effectiveProfile: CameraProfile = useMemo(() => {
    if (isEdit && camera?.profile) return camera.profile
    if (me?.sector && me.sector !== "both") return me.sector
    return profile
  }, [isEdit, camera?.profile, me?.sector, profile])
  const { data: ppeMeta, isLoading: ppeLoading, isError: ppeError } = usePPEClassesMeta(effectiveProfile)
  const defaultEnabled = useMemo<string[]>(() => ppeMeta?.default_enabled?.length ? ppeMeta.default_enabled : effectiveProfile === "medical" ? ["mask", "gloves", "cap"] : ["helmet", "vest"], [ppeMeta, effectiveProfile])
  const allowedKeys = useMemo<Set<string>>(() => new Set((ppeMeta?.allowed ?? defaultEnabled).map(String)), [ppeMeta, defaultEnabled])
  const placeholder = useMemo(() => {
    if (isEdit) return "اتركه فارغًا للإبقاء على المصدر الحالي؛ أدخل مصدرًا جديدًا عند التغيير"
    if (sourceType === "webcam") return "رقم الكاميرا مثل 0 أو 1"
    if (sourceType === "rtsp") return "rtsp://user:pass@عنوان-الكاميرا/..."
    return "مسار ملف فيديو داخل مجلد الفيديو المسموح"
  }, [isEdit, sourceType])

  useEffect(() => {
    if (isEdit) return
    if (enabled.length === 0) setEnabled(defaultEnabled)
    // Initialize defaults once the profile metadata is loaded.
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
    return Array.from(new Set((values ?? []).map(String).filter((key) => allowedKeys.has(key))))
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    if (sourceType === "webcam" && sourceUri.trim() && !/^\d+$/.test(sourceUri.trim())) {
      setError("بالنسبة لكاميرا الويب، أدخل رقمًا مثل 0 أو 1.")
      return
    }

    const enabledClean = sanitizeEnabled(enabled)
    const finalEnabled = enabledClean.length ? enabledClean : defaultEnabled

    try {
      if (isEdit && camera) {
        await updateMut.mutateAsync({
          id: camera.id,
          payload: { name: name.trim(), ...(sourceUri.trim() ? { source_uri: sourceUri.trim() } : {}), enabled_classes: finalEnabled },
        })
      } else {
        await createMut.mutateAsync({ name: name.trim(), source_type: sourceType, source_uri: sourceUri.trim(), profile: effectiveProfile, enabled_classes: finalEnabled })
        setName("")
        setSourceUri(sourceType === "webcam" ? "0" : "")
        setEnabled(defaultEnabled)
      }
      onSuccess?.()
    } catch (reason) {
      setError(getErrorMessage(reason, isEdit ? "فشل تحديث الكاميرا" : "فشل إضافة الكاميرا"))
    }
  }

  return (
    <Card className="border-0 shadow-none">
      <CardContent className="p-0">
        <form onSubmit={submit} className="space-y-5">
          <ol className="grid grid-cols-2 gap-2" aria-label="خطوات إعداد الكاميرا">
            <li className="flex items-center gap-2 rounded-xl bg-primary-light px-3 py-2.5 text-xs font-semibold text-primary"><span className="flex size-6 items-center justify-center rounded-full bg-primary text-[11px] text-primary-foreground">1</span>المصدر والقطاع</li>
            <li className="flex items-center gap-2 rounded-xl bg-muted px-3 py-2.5 text-xs font-semibold text-muted-foreground"><span className="flex size-6 items-center justify-center rounded-full bg-card text-[11px]">2</span>قواعد الوقاية</li>
          </ol>

          <section aria-labelledby="camera-source-title" className="space-y-3.5">
            <h3 id="camera-source-title" className="flex items-center gap-2 text-sm font-bold"><Camera className="size-4 text-primary" /> مصدر الفيديو</h3>
            <div className="space-y-1.5">
              <label htmlFor="camera-name" className="text-xs font-semibold text-foreground">اسم الكاميرا</label>
              <Input id="camera-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="مثال: بوابة الموقع الرئيسية" required maxLength={100} className="min-h-11 rounded-xl" />
            </div>

            {!isEdit && me?.sector === "both" && (
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">القطاع</label>
                <Select value={effectiveProfile} onValueChange={(value) => setProfile(value as CameraProfile)}>
                  <SelectTrigger className="min-h-11 w-full rounded-xl"><SelectValue placeholder="اختر القطاع" /></SelectTrigger>
                  <SelectContent><SelectItem value="construction">الإنشاءات</SelectItem><SelectItem value="medical">القطاع الطبي</SelectItem></SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-foreground">نوع المصدر</label>
              {isEdit ? <div className="flex min-h-11 items-center rounded-xl border border-input bg-muted/40 px-3 text-sm text-muted-foreground">{SOURCE_TYPE_LABELS[sourceType]} · غير قابل للتعديل</div> : (
                <Select value={sourceType} onValueChange={(value) => setSourceType(value as CameraSourceType)}>
                  <SelectTrigger className="min-h-11 w-full rounded-xl"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="webcam">{SOURCE_TYPE_LABELS.webcam}</SelectItem><SelectItem value="rtsp">{SOURCE_TYPE_LABELS.rtsp}</SelectItem><SelectItem value="file">{SOURCE_TYPE_LABELS.file}</SelectItem></SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-1.5">
              <label htmlFor="camera-source-uri" className="text-xs font-semibold text-foreground">عنوان أو مسار المصدر</label>
              <Input id="camera-source-uri" dir="ltr" type={sourceType === "webcam" ? "number" : "text"} value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} placeholder={placeholder} required={!isEdit} autoComplete="off" spellCheck={false} className="min-h-11 rounded-xl text-start" />
              <p className="text-[11px] leading-5 text-muted-foreground">تُرسل بيانات المصدر مباشرة إلى الخادم ولا تُعرض في بطاقات الكاميرات. استخدم مصادر مسموحًا بها من إعدادات الخادم.</p>
            </div>
          </section>

          <section aria-labelledby="camera-ppe-title" className="space-y-3 border-t border-border/70 pt-4">
            <div className="flex items-start gap-2.5">
              <ShieldCheck className="mt-0.5 size-4 text-primary" />
              <div><h3 id="camera-ppe-title" className="text-sm font-bold">ما الذي تريد مراقبته؟</h3><p className="mt-1 text-xs text-muted-foreground">اختر قواعد معدات الوقاية المناسبة لهذا القطاع.</p></div>
            </div>
            {ppeLoading ? <div className="skeleton-shimmer h-20 rounded-xl" role="status" aria-label="جارٍ تحميل قواعد الوقاية" /> : ppeError || !ppeMeta ? <div role="alert" className="rounded-xl bg-destructive-light p-3 text-sm text-destructive-foreground">تعذّر تحميل قائمة معدات الوقاية.</div> : <PpeClassPicker items={ppeMeta.items} value={enabled} onChange={setEnabled} />}
          </section>

          {error && <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive-light px-3 py-2.5 text-sm text-destructive-foreground">{error}</p>}
          <Button disabled={pending || ppeLoading || ppeError} type="submit" className="min-h-12 w-full rounded-xl">
            {pending ? "جارٍ الحفظ..." : isEdit ? "حفظ التعديلات" : "إضافة الكاميرا"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
