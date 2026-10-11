import { useEffect, useMemo, useState } from "react"
import PpeClassPicker from "@/components/PpeClassPicker"
import { useCreateCamera, useMe, usePPEClassesMeta, useUpdateCamera } from "@/hooks/useNexora"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getErrorMessage } from "@/lib/utils"
import type { Camera, CameraSourceType, CameraProfile } from "@/types"

const SOURCE_TYPE_LABELS: Record<CameraSourceType, string> = {
  webcam: "كاميرا ويب (Webcam)",
  rtsp: "بث شبكي (RTSP)",
  file: "ملف فيديو",
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
  const [sourceUri, setSourceUri] = useState(camera?.source_uri ?? "")
  const [enabled, setEnabled] = useState<string[]>(camera?.enabled_classes ?? [])
  const [error, setError] = useState<string | null>(null)

  const [profile, setProfile] = useState<CameraProfile>((camera?.profile as CameraProfile) ?? "construction")

  const effectiveProfile: CameraProfile = useMemo(() => {
    if (isEdit && camera?.profile) return camera.profile
    if (me?.sector && me.sector !== "both") return me.sector
    return profile
  }, [isEdit, camera?.profile, me?.sector, profile])

  const { data: ppeMeta, isLoading: ppeLoading, isError: ppeError } = usePPEClassesMeta(effectiveProfile)

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
    if (sourceType === "webcam") return "Webcam index مثل: 0 أو 1"
    if (sourceType === "rtsp") return "rtsp://user:pass@ip:554/..."
    return "مسار ملف فيديو مثل: C:\\videos\\test.mp4"
  }, [sourceType])

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

    if (sourceType === "webcam" && !/^\d+$/.test(sourceUri.trim())) {
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
            source_uri: sourceUri.trim(),
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
        <form onSubmit={submit} className="space-y-3">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="اسم الكاميرا" required />

          {!isEdit && me?.sector === "both" && (
            <Select value={effectiveProfile} onValueChange={(v) => setProfile(v as CameraProfile)}>
              <SelectTrigger className="h-9 w-full rounded-lg">
                <SelectValue placeholder="نوع العميل" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="construction">Construction</SelectItem>
                <SelectItem value="medical">Medical</SelectItem>
              </SelectContent>
            </Select>
          )}

          {isEdit ? (
            <div className="flex h-9 items-center rounded-lg border border-input bg-muted/40 px-3 text-sm text-muted-foreground">
              نوع المصدر: {SOURCE_TYPE_LABELS[sourceType]} (غير قابل للتعديل)
            </div>
          ) : (
            <Select value={sourceType} onValueChange={(v) => setSourceType(v as CameraSourceType)}>
              <SelectTrigger className="h-9 w-full rounded-lg">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="webcam">{SOURCE_TYPE_LABELS.webcam}</SelectItem>
                <SelectItem value="rtsp">{SOURCE_TYPE_LABELS.rtsp}</SelectItem>
                <SelectItem value="file">{SOURCE_TYPE_LABELS.file}</SelectItem>
              </SelectContent>
            </Select>
          )}

          <Input
            type={sourceType === "webcam" ? "number" : "text"}
            value={sourceUri}
            onChange={(e) => setSourceUri(e.target.value)}
            placeholder={placeholder}
            required
          />

          <div className="pt-2">
            <div className="text-sm font-semibold mb-2">ما الذي تريد مراقبته؟</div>

            {ppeLoading ? (
              <div className="text-sm text-muted-foreground">جاري تحميل عناصر PPE...</div>
            ) : ppeError || !ppeMeta ? (
              <div className="text-sm text-destructive">تعذّر تحميل قائمة معدات الوقاية</div>
            ) : (
              <PpeClassPicker items={ppeMeta.items} value={enabled} onChange={setEnabled} />
            )}
          </div>

          <Button disabled={pending} type="submit" className="w-full">
            {pending ? "جارٍ الحفظ..." : isEdit ? "حفظ التعديلات" : "إضافة الكاميرا"}
          </Button>

          {error && <div className="text-sm text-destructive">{error}</div>}
        </form>
      </CardContent>
    </Card>
  )
}