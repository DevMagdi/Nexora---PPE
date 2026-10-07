import { useEffect, useMemo, useState } from "react"
import PpeClassPicker from "@/components/PpeClassPicker"
import { useCreateCamera } from "@/hooks/useNexora"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import type { CameraSourceType } from "@/types"

export default function AddCameraForm() {
  const createMut = useCreateCamera()

  const [name, setName] = useState("")
  const [sourceType, setSourceType] = useState<CameraSourceType>("rtsp")
  const [sourceUri, setSourceUri] = useState("")
  const [enabled, setEnabled] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const placeholder = useMemo(() => {
    if (sourceType === "webcam") return "Webcam index مثل: 0 أو 1"
    if (sourceType === "rtsp") return "rtsp://user:pass@ip:554/..."
    return "مسار ملف فيديو مثل: C:\\videos\\test.mp4"
  }, [sourceType])

  // default webcam index
  useEffect(() => {
    if (sourceType === "webcam") {
      if (!/^\d+$/.test(sourceUri)) setSourceUri("0")
    }
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
      await createMut.mutateAsync({
        name: name.trim(),
        source_type: sourceType,
        source_uri: sourceUri.trim(),
        enabled_classes: enabled,
      })

      setName("")
      setSourceUri(sourceType === "webcam" ? "0" : "")
      setEnabled([])
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "فشل إضافة الكاميرا")
    }
  }

  return (
    <Card className="border-0 shadow-none">
      <CardContent className="p-0">
        <form onSubmit={submit} className="space-y-3">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="اسم الكاميرا" required />

          <select
            className="h-9 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as CameraSourceType)}
          >
            <option value="webcam">Webcam</option>
            <option value="rtsp">RTSP</option>
            <option value="file">Video File</option>
          </select>

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

          <Button disabled={createMut.isPending} type="submit" className="w-full">
            {createMut.isPending ? "Saving..." : "Add Camera"}
          </Button>

          {error && <div className="text-sm text-destructive">{error}</div>}
        </form>
      </CardContent>
    </Card>
  )
}