import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { InlineError } from "@/components/Feedback"
import RulePicker from "@/components/RulePicker"
import { createCamera, updateCamera } from "@/lib/api"
import type { Camera, RuleKey, Site } from "@/types"

export default function CameraForm({
  camera,
  sites,
  onSuccess,
}: {
  camera?: Camera
  sites: Site[]
  onSuccess: () => void
}) {
  const [name, setName] = useState(camera?.name ?? "")
  const [uri, setUri] = useState("")
  const [site, setSite] = useState(camera?.site_id?.toString() ?? "")
  const [rules, setRules] = useState<RuleKey[]>(camera?.enabled_classes ?? ["helmet", "vest"])
  const mutation = useMutation({
    mutationFn: () =>
      camera
        ? updateCamera(camera.id, {
            name,
            ...(uri ? { source_uri: uri } : {}),
            site_id: site ? Number(site) : null,
            enabled_classes: rules,
          })
        : createCamera({
            name,
            source_type: "rtsp",
            source_uri: uri,
            site_id: site ? Number(site) : null,
            enabled_classes: rules,
          }),
    onSuccess,
  })
  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <div>
        <label htmlFor="camera-name" className="field-label">
          اسم الكاميرا
        </label>
        <input
          id="camera-name"
          className="field"
          placeholder="مثال: بوابة خط الإنتاج"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={100}
        />
      </div>
      <div>
        <label htmlFor="camera-site" className="field-label">
          المصنع أو الموقع
        </label>
        <select
          id="camera-site"
          className="field"
          value={site}
          onChange={(e) => setSite(e.target.value)}
        >
          <option value="">غير معيّن</option>
          {sites.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </div>
      {camera?.source_type !== "file" && (
        <div>
          <label htmlFor="camera-uri" className="field-label">
            {camera ? "تغيير رابط RTSP (اختياري)" : "رابط بث RTSP"}
          </label>
          <input
            id="camera-uri"
            className="field latin"
            dir="ltr"
            placeholder="rtsp://camera-address:554/stream"
            value={uri}
            onChange={(e) => setUri(e.target.value)}
            required={!camera}
            pattern="rtsps?://.+"
            maxLength={500}
            autoComplete="off"
          />
          <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
            {camera
              ? "لأمان بيانات الكاميرا، لا نعرض الرابط الأصلي. اتركه فارغاً للاحتفاظ به. تغيير المصدر يوقف البث حتى تشغيله مجدداً."
              : "يجب أن يكون العنوان ضمن قائمة شبكات الكاميرات المسموح بها على الخادم."}
          </p>
        </div>
      )}
      <RulePicker value={rules} onChange={setRules} disabled={mutation.isPending} />
      <InlineError error={mutation.error} />
      <Button type="submit" className="w-full" disabled={mutation.isPending || !rules.length}>
        {mutation.isPending ? <Loader2 className="animate-spin" /> : <Save />}
        {camera ? "حفظ التعديلات" : "إضافة الكاميرا"}
      </Button>
    </form>
  )
}
