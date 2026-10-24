import { useRef, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { ArrowUpLeft, Image, Loader2, ScanLine, Upload, Video } from "lucide-react"
import { Button } from "@/components/ui/button"
import { InlineError } from "@/components/Feedback"
import RulePicker from "@/components/RulePicker"
import { inferImage, uploadVideo } from "@/lib/api"
import { classLabel, num } from "@/lib/formatters"
import type { Camera, ImageResult, RuleKey, Site, SystemMeta } from "@/types"

export default function UploadsPage({
  sites,
  meta,
  refresh,
  onLive,
}: {
  sites: Site[]
  meta?: SystemMeta
  refresh: () => Promise<void>
  onLive: (id: number) => void
}) {
  const alertConfidence = meta?.effective_negative_confidence ?? meta?.negative_confidence
  const [mode, setMode] = useState<"image" | "video">("image")
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState("")
  const [site, setSite] = useState("")
  const [rules, setRules] = useState<RuleKey[]>(["helmet", "vest"])
  const [validation, setValidation] = useState<string | null>(null)
  const [image, setImage] = useState<ImageResult | null>(null)
  const [camera, setCamera] = useState<Camera | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("اختر ملفاً أولاً")
      const body = new FormData()
      body.append("file", file)
      body.append("enabled_classes", rules.join(","))
      if (mode === "image") {
        const result = await inferImage(body)
        setImage(result)
      } else {
        body.append("name", name.trim())
        if (site) body.append("site_id", site)
        const result = await uploadVideo(body)
        setCamera(result)
        await refresh()
      }
    },
  })
  function choose(file: File | null) {
    setValidation(null)
    setImage(null)
    setCamera(null)
    mutation.reset()
    if (file && meta && file.size > meta.max_upload_mb * 1024 * 1024) {
      setValidation(`الحد الأقصى للرفع ${meta.max_upload_mb} ميجابايت`)
      setFile(null)
      if (input.current) input.current.value = ""
      return
    }
    setFile(file)
  }
  return (
    <div className="grid items-start gap-7 lg:grid-cols-[390px_1fr]">
      <section className="panel p-6">
        <div className="segmented mb-6">
          <button
            disabled={mutation.isPending}
            aria-pressed={mode === "image"}
            onClick={() => {
              setMode("image")
              choose(null)
              if (input.current) input.current.value = ""
            }}
          >
            <Image className="me-2 inline size-4" />
            صورة
          </button>
          <button
            disabled={mutation.isPending}
            aria-pressed={mode === "video"}
            onClick={() => {
              setMode("video")
              choose(null)
              if (input.current) input.current.value = ""
            }}
          >
            <Video className="me-2 inline size-4" />
            فيديو
          </button>
        </div>
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault()
            setValidation(null)
            setImage(null)
            setCamera(null)
            mutation.mutate()
          }}
        >
          <div className="rounded-lg border border-dashed border-border bg-muted p-6 text-center">
            <Upload className="mx-auto mb-4 size-8 text-muted-foreground" strokeWidth={1.3} />
            <label htmlFor="industrial-upload" className="mb-3 block text-sm text-foreground">
              {mode === "image" ? "اختر صورة من موقع العمل" : "اختر مقطع فيديو من الموقع"}
            </label>
            <input
              ref={input}
              id="industrial-upload"
              className="w-full text-[11px] text-muted-foreground file:me-3 file:cursor-pointer file:rounded-lg file:border file:border-border file:bg-card file:px-3 file:py-2 file:text-muted-foreground"
              type="file"
              required
              disabled={mutation.isPending}
              accept={mode === "image" ? "image/jpeg,image/png" : ".mp4,.avi"}
              onChange={(event) => choose(event.target.files?.[0] ?? null)}
            />
            <p className="latin mt-3 text-[9px] text-muted-foreground">
              {mode === "image" ? "JPEG / PNG" : "MP4 / AVI"}
              {meta ? ` · MAX ${meta.max_upload_mb} MB` : ""}
            </p>
          </div>
          {mode === "video" && (
            <>
              <div>
                <label htmlFor="video-name" className="field-label">
                  اسم مصدر الفيديو
                </label>
                <input
                  id="video-name"
                  className="field"
                  required
                  maxLength={100}
                  disabled={mutation.isPending}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="مثال: منطقة التحميل — وردية الصباح"
                />
              </div>
              <div>
                <label htmlFor="upload-site" className="field-label">
                  الموقع
                </label>
                <select
                  id="upload-site"
                  className="field"
                  disabled={mutation.isPending}
                  value={site}
                  onChange={(event) => setSite(event.target.value)}
                >
                  <option value="">غير معيّن</option>
                  {sites.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
          <RulePicker
            value={rules}
            onChange={setRules}
            disabled={mutation.isPending}
            supportedNegativeRules={meta?.supported_negative_rules}
          />
          <InlineError error={validation || mutation.error} />
          <Button
            className="w-full"
            type="submit"
            disabled={!file || !rules.length || mutation.isPending}
          >
            {mutation.isPending ? <Loader2 /> : <ScanLine />}
            {mutation.isPending
              ? "جارٍ المعالجة…"
              : mode === "image"
                ? "تحليل الصورة"
                : "رفع الفيديو وإعداد المصدر"}
          </Button>
          <p className="text-[10px] leading-[1.9] text-muted-foreground">
            {mode === "image"
              ? "الصورة تُحلّل مرة واحدة ولا تُنشئ تنبيهاً زمنياً. استخدم البث أو الفيديو لتوثيق المخالفات المستمرة."
              : `الفيديو يُضاف كمصدر للمراقبة ويُحلّل مرة واحدة بمعدل إطاراته الأصلي. شغّله من صفحة البث. ${meta ? `مدة الرفع القصوى ${meta.max_video_seconds} ثانية.` : ""}`}
          </p>
        </form>
      </section>
      <section className="panel min-w-0 overflow-hidden">
        <div className="panel-header">
          <div>
            <h2>نتائج التحليل</h2>
            <p>
              الوزن المعتمد {meta?.model ?? "ppe.pt"} · حد الثقة{" "}
              {meta ? `${Math.round(meta.confidence * 100)}%` : "—"}
              {alertConfidence
                ? ` · السالب للتنبيه ${Math.round(alertConfidence * 100)}% + ثبات زمني`
                : ""}
            </p>
          </div>
        </div>
        {image ? (
          <>
            <img
              className="max-h-[500px] w-full bg-muted object-contain"
              src={image.preview}
              alt="نتيجة رصد معدات الوقاية في الصورة المرفوعة"
            />
            <div className="p-6">
              <p className="source-help mb-4">
                حُسمت التصنيفات المتعارضة قبل الرسم. الذهبي للمعدات، الفاتح للشخص، والأحمر للتصنيف
                السلبي. الصورة معاينة فقط ولا تُنشئ حدث مخالفة.
              </p>
              <p className="mb-4 text-xs text-muted-foreground">
                {num(image.detections.length)} كشف ·{" "}
                <span className="latin">
                  {image.width} × {image.height}
                </span>
              </p>
              <div className="flex flex-wrap gap-2">
                {image.detections.map((item, index) => (
                  <span
                    key={`${item.class_name}-${index}`}
                    className={`badge ${item.class_name.startsWith("NO-") ? "badge-danger" : ""}`}
                  >
                    {classLabel(item.class_name)}
                    <span className="latin">{Math.round(item.confidence * 100)}%</span>
                  </span>
                ))}
                {!image.detections.length && (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    لم تُرصد عناصر فوق حد الثقة للفئات المختارة. لا يعني ذلك إثبات الالتزام.
                  </p>
                )}
              </div>
            </div>
          </>
        ) : camera ? (
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true">
              <Video />
            </span>
            <h3>تم تجهيز مصدر الفيديو</h3>
            <p>«{camera.name}» جاهز لبدء المعالجة عبر نفس كاشف معدات الوقاية.</p>
            <Button onClick={() => onLive(camera.id)}>
              الانتقال إلى المراقبة
              <ArrowUpLeft />
            </Button>
          </div>
        ) : (
          <div className="empty-state min-h-[420px]">
            <span className="empty-state-icon" aria-hidden="true">
              <ScanLine />
            </span>
            <h3>{mutation.isPending ? "جارٍ معالجة الملف" : "بانتظار ملف من موقعك"}</h3>
            <p>
              ستظهر نتائج الموديل الفعلية هنا بعد الرفع. لا توجد نتائج أو بيانات تجريبية مضمّنة.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}
