import axios from "axios"
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getErrorMessage(error: unknown, fallback = "حدث خطأ غير متوقع"): string {
  if (typeof error === "string") return error
  if (axios.isAxiosError(error)) {
    if (!error.response || error.response.status >= 500)
      return "تعذّر الاتصال بالخادم. تحقّق من تشغيل الخدمة والموديل المعتمد ثم أعد المحاولة."
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string") {
      if (detail.includes("ALLOWED_HTTP_CAMERA_PREFIXES"))
        return "مصدر HTTP أو أحد موارد HLS خارج القائمة المسموحة أو غير مفعّل؛ راجع إعدادات الخادم."
      if (detail.includes("ALLOWED_RTSP_PREFIXES"))
        return "عنوان RTSP خارج شبكة الكاميرات المسموحة أو لم تُضبط القائمة على الخادم."
      if (detail.includes("ALLOWED_VIDEO_DIR"))
        return "مسار الفيديو غير مسموح؛ استخدم ملفًا داخل مجلد الفيديو المحدد على الخادم."
      if (detail.includes("USB") || detail.includes("ALLOWED_USB_DEVICE_INDICES"))
        return "USB للتطوير المحلي فقط، ويحتاج تفعيلًا وفهرس جهاز مسموحًا على الخادم."
      if (detail.includes("HLS source URI") || detail.includes("match the URI scheme"))
        return "نوع المصدر لا يطابق الرابط؛ HLS يحتاج HTTP(S) بامتداد m3u8 وRTSP يحتاج البروتوكول المطابق."
      if (detail.includes("Port field conflicts"))
        return "المنفذ لا يطابق المنفذ المكتوب داخل الرابط؛ صحّح أحدهما."
      return detail
    }
    if (detail && typeof detail === "object" && "message" in detail) {
      const message = (detail as { message?: unknown }).message
      if (typeof message === "string") return message
    }

    if (error.response?.status === 401) {
      return "بيانات الدخول غير صحيحة أو انتهت الجلسة. من فضلك سجّل الدخول مرة أخرى."
    }
    if (error.response?.status === 429) {
      return "محاولات كثيرة؛ انتظر قليلاً ثم حاول مرة أخرى."
    }
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  return fallback
}
