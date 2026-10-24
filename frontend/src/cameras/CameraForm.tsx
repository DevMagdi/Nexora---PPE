import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { InlineError } from "@/components/Feedback"
import RulePicker from "@/components/RulePicker"
import { SOURCE_OPTIONS, validateSourceInput } from "@/cameras/sources"
import { createCamera, updateCamera } from "@/lib/api"
import type {
  Camera,
  CameraSourceFields,
  CameraSourceType,
  RuleKey,
  Site,
  SystemMeta,
} from "@/types"

export default function CameraForm({
  camera,
  sites,
  meta,
  onSuccess,
}: {
  camera?: Camera
  sites: Site[]
  meta?: SystemMeta
  onSuccess: () => void
}) {
  const [kind, setKind] = useState<CameraSourceType>(camera?.source_type ?? "rtsp")
  const [name, setName] = useState(camera?.name ?? "")
  const [uri, setUri] = useState("")
  const [port, setPort] = useState("")
  const [device, setDevice] = useState(camera?.device_index ?? meta?.usb_device_indices[0] ?? 0)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [clearCredentials, setClearCredentials] = useState(false)
  const [auth, setAuth] = useState<"basic" | "digest">(camera?.auth_mode ?? "basic")
  const [onvif, setOnvif] = useState(camera?.onvif_device_uri ?? "")
  const [site, setSite] = useState(camera?.site_id?.toString() ?? "")
  const [rules, setRules] = useState<RuleKey[]>(camera?.enabled_classes ?? ["helmet", "vest"])
  const [formError, setFormError] = useState<string | null>(null)
  const network = !["file", "usb"].includes(kind)
  const http = kind === "http_mjpeg" || kind === "hls"
  const changedType = Boolean(camera && camera.source_type !== kind)
  const option = SOURCE_OPTIONS.find((item) => item.value === kind)!
  const usbDisabled = kind === "usb" && !meta?.usb_sources_enabled
  const mutation = useMutation({
    mutationFn: () => {
      const source: CameraSourceFields = {
        ...(uri ? { source_uri: uri.trim() } : {}),
        ...(kind === "usb" ? { device_index: device } : {}),
        ...(network && port ? { port: Number(port) } : {}),
        ...(network && username && !clearCredentials
          ? { source_username: username, source_password: password }
          : {}),
        ...(network && clearCredentials ? { clear_credentials: true } : {}),
        ...(http && (!camera || changedType || auth !== camera.auth_mode)
          ? { auth_mode: auth }
          : {}),
        ...(network && onvif !== (camera?.onvif_device_uri ?? "")
          ? { onvif_device_uri: onvif || null }
          : {}),
      }
      const common = {
        name,
        site_id: site ? Number(site) : null,
        enabled_classes: rules,
        ...source,
      }
      return camera
        ? updateCamera(camera.id, { ...common, ...(changedType ? { source_type: kind } : {}) })
        : createCamera({ ...common, source_type: kind })
    },
    onSuccess,
  })
  return (
    <form
      className="form-section"
      aria-busy={mutation.isPending}
      onSubmit={(event) => {
        event.preventDefault()
        const error = validateSourceInput(kind, uri.trim())
        if (error) {
          setFormError(error)
          return
        }
        if (network && !clearCredentials && Boolean(username) !== Boolean(password)) {
          setFormError("أدخل اسم المستخدم وكلمة المرور معًا، أو اتركهما فارغين.")
          return
        }
        if (usbDisabled) {
          setFormError("USB غير مفعّل؛ متاح للتطوير المحلي فقط.")
          return
        }
        setFormError(null)
        mutation.mutate()
      }}
    >
      <div>
        <label htmlFor="camera-source-type" className="field-label">
          نوع المصدر
        </label>
        <select
          id="camera-source-type"
          className="field"
          value={kind}
          aria-describedby="camera-source-help"
          onChange={(event) => {
            setKind(event.target.value as CameraSourceType)
            setUri("")
            setPort("")
            setUsername("")
            setPassword("")
            setAuth("basic")
            setClearCredentials(false)
            setOnvif("")
            setFormError(null)
            mutation.reset()
          }}
        >
          {SOURCE_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <p id="camera-source-help" className="source-help mt-3">
          {option.hint}
        </p>
        {usbDisabled && (
          <p className="notice mt-3" role="status">
            USB غير مفعّل على هذا الخادم. متاح للتطوير المحلي فقط، وليس مصدرًا للإنتاج.
          </p>
        )}
        {http && meta && !meta.http_sources_enabled && (
          <p className="notice mt-3">
            مصادر HTTP مغلقة حاليًا؛ يجب أن يضبط مسؤول الخادم ALLOWED_HTTP_CAMERA_PREFIXES أولًا.
          </p>
        )}
      </div>
      <div className="grid gap-6 sm:grid-cols-2">
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
      </div>
      {kind === "usb" ? (
        <div>
          <label htmlFor="camera-device-index" className="field-label">
            فهرس جهاز USB على الخادم
          </label>
          <input
            id="camera-device-index"
            className="field latin"
            dir="ltr"
            type="number"
            min={0}
            max={15}
            step={1}
            required
            value={device}
            disabled={usbDisabled}
            onChange={(e) => setDevice(Number(e.target.value))}
          />
          <p className="source-help mt-2">
            الفهارس المسموحة: {meta?.usb_device_indices.join(", ") || "لا يوجد جهاز مصرح به"}. لم
            يُختبر توصيل جهازك تلقائيًا.
          </p>
        </div>
      ) : (
        <div>
          <label htmlFor="camera-uri" className="field-label">
            {kind === "file"
              ? "مسار ملف الفيديو على الخادم"
              : `رابط ${kind === "http_mjpeg" ? "MJPEG" : kind.toUpperCase()}`}
            {camera && !changedType ? " (اختياري للتغيير)" : ""}
          </label>
          <input
            id="camera-uri"
            className="field latin"
            dir="ltr"
            placeholder={option.placeholder}
            value={uri}
            onChange={(e) => setUri(e.target.value)}
            required={!camera || changedType}
            maxLength={500}
            autoComplete="off"
            aria-describedby="camera-uri-help"
          />
          <p id="camera-uri-help" className="source-help mt-2">
            {camera && !changedType
              ? "لا نعرض الرابط أو المسار الأصلي. اترك الحقل فارغًا للاحتفاظ به؛ تغيير المصدر يوقف البث حتى تشغيله مجددًا."
              : network
                ? "العنوان وكل موارد HLS يجب أن تقع داخل القائمة المسموحة. لا تُقبل إعادة توجيه HTTP."
                : "هذا مسار على الخادم وليس على جهاز المتصفح."}
          </p>
        </div>
      )}
      {network && (
        <>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="camera-port" className="field-label">
                المنفذ (اختياري)
              </label>
              <input
                id="camera-port"
                className="field latin"
                dir="ltr"
                type="number"
                min={1}
                max={65535}
                placeholder={kind === "rtsp" ? "554" : kind === "rtsps" ? "322" : "80 / 443"}
                value={port}
                onChange={(e) => setPort(e.target.value)}
              />
            </div>
            {http && (
              <div>
                <label htmlFor="camera-auth-mode" className="field-label">
                  مصادقة HTTP
                </label>
                <select
                  id="camera-auth-mode"
                  className="field latin"
                  dir="ltr"
                  value={auth}
                  onChange={(e) => setAuth(e.target.value as "basic" | "digest")}
                >
                  <option value="basic">Basic — يُفضّل HTTPS</option>
                  <option value="digest">Digest</option>
                </select>
              </div>
            )}
          </div>
          <fieldset className="form-section border-0 p-0">
            <legend className="field-label mb-3">
              بيانات الاتصال — إدخال فقط، لا تُعاد من الخادم
            </legend>
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <label htmlFor="camera-username" className="field-label">
                  اسم مستخدم الكاميرا
                </label>
                <input
                  id="camera-username"
                  className="field latin"
                  dir="ltr"
                  value={username}
                  disabled={clearCredentials}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                  maxLength={128}
                />
              </div>
              <div>
                <label htmlFor="camera-password" className="field-label">
                  كلمة مرور الكاميرا
                </label>
                <input
                  id="camera-password"
                  className="field latin"
                  dir="ltr"
                  type="password"
                  value={password}
                  disabled={clearCredentials}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  maxLength={128}
                />
              </div>
            </div>
            <p className="source-help">
              لا تُعرض بيانات الدخول المحفوظة ولا تُعبّأ تلقائيًا.{" "}
              {camera
                ? "ترك الرابط والبيانات فارغة يحتفظ بالمحفوظ؛ إدخال رابط جديد لا ينسخ كلمة المرور القديمة إليه."
                : "اتركهما فارغين إذا كان المصدر بلا مصادقة."}{" "}
              {http
                ? "لا تُرسل المصادقة إلى نطاق آخر داخل HLS؛ لا تستخدم كلمات مرور داخل الاستعلامات."
                : "يتفاوض مفكّك RTSP مع مصادقة الجهاز مباشرة."}
            </p>
            {camera && (
              <label className="flex items-center gap-3 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={clearCredentials}
                  onChange={(e) => setClearCredentials(e.target.checked)}
                />
                حذف بيانات مصادقة المصدر المحفوظة
              </label>
            )}
          </fieldset>
          <details className="notice">
            <summary>عنوان جهاز ONVIF — تسجيل فقط، بلا اكتشاف تلقائي</summary>
            <div className="mt-4">
              <label htmlFor="camera-onvif" className="field-label">
                عنوان خدمة ONVIF (اختياري)
              </label>
              <input
                id="camera-onvif"
                className="field latin"
                dir="ltr"
                placeholder="http://192.168.10.20/onvif/device_service"
                value={onvif}
                onChange={(e) => setOnvif(e.target.value)}
                maxLength={500}
                autoComplete="off"
              />
              <p className="source-help mt-3">
                يُحفظ كبيانات تعريف ضمن قائمة HTTP المسموحة، ولا يتصل به النظام لاكتشاف الأجهزة أو
                استخراج الفيديو. استخرج RTSP من إعدادات الكاميرا أو أداة ONVIF موثوقة ثم أدخله في
                حقل المصدر.
              </p>
            </div>
          </details>
        </>
      )}
      <RulePicker value={rules} onChange={setRules} disabled={mutation.isPending} />
      {formError && (
        <p className="notice notice-error" role="alert">
          {formError}
        </p>
      )}
      <InlineError error={mutation.error} />
      <Button
        type="submit"
        className="w-full"
        disabled={mutation.isPending || !rules.length || usbDisabled}
      >
        {mutation.isPending ? <Loader2 /> : <Save />}
        {mutation.isPending ? "جارٍ الحفظ…" : camera ? "حفظ التعديلات" : "إضافة الكاميرا"}
      </Button>
    </form>
  )
}
