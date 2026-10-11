import { useEffect, useMemo, useState } from "react"
import PpeClassPicker from "@/components/PpeClassPicker"
import { useCreateCamera, useUpdateCamera, usePPEClassesMeta } from "@/hooks/useNexora"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getErrorMessage } from "@/lib/utils"
import type { Camera, CameraSourceType } from "@/types"

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
  const { data: ppeMeta } = usePPEClassesMeta()

  const isEdit = mode === "edit" && camera !== undefined
  const pending = isEdit ? updateMut.isPending : createMut.isPending

  const defaultEnabled = useMemo<string[]>(
    () => (ppeMeta?.default_enabled?.length ? ppeMeta.default_enabled : ["helmet", "vest"]),
    [ppeMeta],
  )

  const allowedKeys = useMemo<Set<string>>(
    () => new Set((ppeMeta?.allowed ?? ["helmet", "vest", "mask", "gloves", "boots", "goggles"]).map(String)),
    [ppeMeta],
  )

  const [name, setName] = useState(camera?.name ?? "")
  const [sourceType, setSourceType] = useState<CameraSourceType>(camera?.source_type ?? "rtsp")
  const [sourceUri, setSourceUri] = useState(camera?.source_uri ?? "")
  const [enabled, setEnabled] = useState<string[]>(camera?.enabled_classes ?? [])
  const [error, setError] = useState<string | null>(null)

  const placeholder = useMemo(() => {
    if (sourceType === "webcam") return "Webcam index مثل: 0 أو 1"
    if (sourceType === "rtsp") return "rtsp://user:pass@ip:554/..."
    return "مسار ملف فيديو مثل: C:\\videos\\test.mp4"
  }, [sourceType])

  // default enabled (create only) لو المستخدم ما اختارش أي حاجة
  useEffect(() => {
    if (isEdit) return
    if (enabled.length === 0) setEnabled(defaultEnabled)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, defaultEnabled])

  // قيمة افتراضية منطقية لـ webcam index — وقت الإنشاء بس
  useEffect(() => {
    if (isEdit) return
    if (sourceType === "webcam" && !/^\d+$/.test(sourceUri)) setSourceUri("0")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceType])

  function sanitizeEnabled(values: string[]) {
    const cleaned = (values ?? []).map(String).filter((k) => allowedKeys.has(k))
    const unique = Array.from(new Set(cleaned))
    return unique
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

    // Debug مؤقت (امسحه بعد ما تتأكد)
    console.log("Submitting enabled_classes =", finalEnabled)

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
            <PpeClassPicker value={enabled} onChange={setEnabled} />
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