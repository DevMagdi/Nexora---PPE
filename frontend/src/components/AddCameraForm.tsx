import { useEffect, useMemo, useState } from "react"
import PpeClassPicker from "@/components/PpeClassPicker"
import { useCreateCamera, useUpdateCamera } from "@/hooks/useNexora"
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
  /** "create" (الافتراضي) لإضافة كاميرا جديدة، أو "edit" لتعديل كاميرا موجودة */
  mode?: "create" | "edit"
  /** مطلوبة في وضع "edit" فقط */
  camera?: Camera
  /** بينفَّذ بعد نجاح الحفظ (إضافة أو تعديل) — الأب هو المسؤول عن قفل الـ Dialog */
  onSuccess?: () => void
}

export default function AddCameraForm({ mode = "create", camera, onSuccess }: Props) {
  const createMut = useCreateCamera()
  const updateMut = useUpdateCamera()

  const isEdit = mode === "edit" && camera !== undefined
  const pending = isEdit ? updateMut.isPending : createMut.isPending

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

  // قيمة افتراضية منطقية لـ webcam index — وقت الإنشاء بس، مش وقت التعديل
  useEffect(() => {
    if (isEdit) return
    if (sourceType === "webcam" && !/^\d+$/.test(sourceUri)) setSourceUri("0")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceType])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (sourceType === "webcam" && !/^\d+$/.test(sourceUri.trim())) {
      setError("بالنسبة للـ Webcam لازم تكتب رقم index مثل 0 أو 1.")
      return
    }

    try {
      if (isEdit && camera) {
        // ✅ الباك إند مايسمحش بتغيير source_type بعد الإنشاء، فمش بنبعته هنا
        await updateMut.mutateAsync({
          id: camera.id,
          payload: {
            name: name.trim(),
            source_uri: sourceUri.trim(),
            enabled_classes: enabled,
          },
        })
      } else {
        await createMut.mutateAsync({
          name: name.trim(),
          source_type: sourceType,
          source_uri: sourceUri.trim(),
          enabled_classes: enabled,
        })
        setName("")
        setSourceUri(sourceType === "webcam" ? "0" : "")
        setEnabled([])
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