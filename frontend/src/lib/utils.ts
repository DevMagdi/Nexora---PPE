import axios from "axios"
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * يستخرج رسالة خطأ مفهومة من أي exception راجع من axios أو غيره.
 * بيدّي أولوية لرسالة الباك إند (detail) لو موجودة، وبعدين لحالة 401
 * تحديدًا (غالبًا يعني مشكلة في VITE_API_KEY)، وآخر حاجة رسالة عامة.
 */
export function getErrorMessage(error: unknown, fallback = "حدث خطأ غير متوقع"): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string") return detail
    if (error.response?.status === 401) {
      return "غير مصرح لك بتنفيذ هذا الإجراء (تحقق من إعداد مفتاح API)"
    }
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  return fallback
}