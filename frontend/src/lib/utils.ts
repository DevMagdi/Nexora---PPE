import axios from "axios"
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getErrorMessage(error: unknown, fallback = "حدث خطأ غير متوقع"): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string") return detail
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