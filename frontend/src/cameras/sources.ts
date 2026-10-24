import type { Camera, CameraSourceType, ConnectionStatus } from "@/types"

export const SOURCE_OPTIONS: {
  value: CameraSourceType
  label: string
  hint: string
  placeholder: string
}[] = [
  {
    value: "rtsp",
    label: "RTSP — الموصى به للمصانع والمواقع",
    hint: "الخيار الافتراضي للإنتاج. فعّل RTSP في الكاميرا وتأكد أن الخادم يصل إليها داخل الشبكة المسموحة.",
    placeholder: "rtsp://192.168.10.20:554/stream",
  },
  {
    value: "rtsps",
    label: "RTSPS — RTSP مشفّر",
    hint: "استخدمه فقط إذا كانت الكاميرا والبنية المحلية تدعمان RTSPS. لا يُحوَّل الرابط إلى RTSP تلقائيًا.",
    placeholder: "rtsps://192.168.10.20:322/stream",
  },
  {
    value: "http_mjpeg",
    label: "HTTP / MJPEG — بث JPEG متتابع",
    hint: "رابط بث multipart MJPEG حقيقي عبر HTTP أو HTTPS؛ ليس صفحة المتصفح أو صورة ثابتة. يلزم تصريح HTTP مستقل على الخادم.",
    placeholder: "http://192.168.10.20:8080/video.mjpg",
  },
  {
    value: "hls",
    label: "HLS — بث ويب بصيغة m3u8",
    hint: "لبث الويب إذا وفّر الجهاز رابط m3u8. يدعم HLS العادي بمسار فيديو مدمج؛ كل قائمة ومقطع ومفتاح يجب أن يكون ضمن المصادر المسموحة. لا يدعم DRM أو LL-HLS.",
    placeholder: "https://camera.example/live/index.m3u8",
  },
  {
    value: "file",
    label: "ملف فيديو — اختبار ومعالجة مرة واحدة",
    hint: "ملف MP4 أو AVI موجود على الخادم داخل ALLOWED_VIDEO_DIR فقط. يُقرأ مرة واحدة ثم تظهر حالة «اكتمل». لرفع ملف من جهازك استخدم صفحة التحليل.",
    placeholder: "samples/site-test.mp4",
  },
  {
    value: "usb",
    label: "USB محلي — تطوير وتجربة فقط",
    hint: "يتصل بجهاز USB الموصول بالخادم، لا بجهاز المتصفح. ممنوع في الإنتاج وstaging؛ يحتاج تفعيلًا صريحًا في بيئة dev وفهرس جهاز مسموحًا.",
    placeholder: "0",
  },
]

export const SOURCE_LABEL = Object.fromEntries(
  SOURCE_OPTIONS.map((item) => [
    item.value,
    item.value === "file"
      ? "VIDEO FILE"
      : item.value === "http_mjpeg"
        ? "MJPEG"
        : item.value.toUpperCase(),
  ]),
) as Record<CameraSourceType, string>

export function sourceIsBusy(camera: Camera): boolean {
  return (
    camera.is_running ||
    camera.connection_status === "starting" ||
    camera.connection_status === "retrying"
  )
}

export function validateSourceInput(kind: CameraSourceType, value: string): string | null {
  if (!value) return null // An unchanged private URI is intentionally never fetched back into the form.
  if (kind === "file")
    return /\.(mp4|avi)$/i.test(value)
      ? null
      : "المسموح ملف MP4 أو AVI داخل مجلد الفيديو على الخادم."
  if (kind === "usb") return null
  try {
    const uri = new URL(value)
    if (
      !uri.hostname ||
      (kind === "rtsp" || kind === "rtsps"
        ? uri.protocol !== `${kind}:`
        : !["http:", "https:"].includes(uri.protocol))
    )
      return "نوع المصدر لا يطابق بروتوكول الرابط."
    const playlist = decodeURIComponent(uri.pathname).toLowerCase().endsWith(".m3u8")
    if (kind === "hls" && !playlist) return "مصدر HLS يحتاج رابط HTTP(S) ينتهي مساره بـ m3u8."
    if (kind === "http_mjpeg" && playlist) return "هذا رابط قائمة HLS؛ اختر HLS بدل MJPEG."
    if (uri.username || uri.password)
      return "استخدم حقلي اسم المستخدم وكلمة المرور بدل وضعهما داخل الرابط."
  } catch {
    return "أدخل رابط مصدر صالحًا مع اسم المضيف والبروتوكول المناسب."
  }
  return null
}

export const CONNECTION_LABEL: Record<ConnectionStatus, string> = {
  starting: "جارٍ الاتصال",
  running: "متصلة",
  retrying: "إعادة اتصال",
  stopped: "متوقفة",
  completed: "اكتمل",
  error: "فشل الاتصال",
}
