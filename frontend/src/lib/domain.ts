import type { ReactNode } from "react"
import type { CameraProfile, Violation } from "@/types"
import type { LiveCounts, LiveMetricItem, RangeKey, TabKey } from "@/types/app"

export const LOCALE = "ar-EG-u-nu-latn"
export const HOUR = 3_600_000
export const DAY = 24 * HOUR
export const VIOLATIONS_FETCH_LIMIT = 200
export const TABLE_PAGE_SIZE = 25
export const MAX_GRID_PREVIEWS = 4

export const CHART_HEX = {
  green: "var(--chart-green)",
  red: "var(--chart-red)",
  amber: "var(--chart-amber)",
  blue: "var(--chart-blue)",
  purple: "var(--chart-purple)",
} as const
export const PIE_COLORS = [CHART_HEX.green, CHART_HEX.blue, CHART_HEX.amber, CHART_HEX.purple, CHART_HEX.red]

export const SECTOR_LABEL: Record<string, string> = {
  construction: "قطاع الإنشاءات",
  medical: "القطاع الطبي",
  both: "إدارة عامة",
}

export const PROFILE_LABEL: Record<CameraProfile, string> = {
  construction: "إنشاءات",
  medical: "طبي",
}

export const ROLE_LABEL: Record<string, string> = {
  admin: "مدير",
  operator: "مشغّل",
  viewer: "مشاهد فقط",
}

export const TAB_TITLES: Record<TabKey, string> = {
  overview: "نظرة عامة",
  live: "المراقبة المباشرة",
  cameras: "إدارة الكاميرات",
  violations: "سجل المخالفات",
}

const CORE_KEYWORDS = ["hardhat", "helmet", "vest", "mask", "glove", "cap", "goggle", "boot", "coat"]

const VIOLATION_LABELS: Record<string, string> = {
  nohardhat: "بدون خوذة",
  nohelmet: "بدون خوذة",
  nosafetyvest: "بدون سترة عاكسة",
  novest: "بدون سترة عاكسة",
  nomask: "بدون كمامة",
  nogloves: "بدون قفازات",
  nohandgloves: "بدون قفازات",
  nogoggles: "بدون نظارات واقية",
  nogoggle: "بدون نظارات واقية",
  nosafetyboots: "بدون حذاء أمان",
  noboots: "بدون حذاء أمان",
  nolabcoat: "بدون بالطو واقي",
  nocoat: "بدون بالطو واقي",
  noheadcap: "بدون غطاء رأس",
  nocap: "بدون غطاء رأس",
}

export function cameraProfile(camera: { profile?: string | null } | null | undefined): CameraProfile {
  return camera?.profile === "medical" ? "medical" : "construction"
}

export function isCoreType(type: string): boolean {
  const normalized = type.toLowerCase()
  return CORE_KEYWORDS.some((keyword) => normalized.includes(keyword))
}

export function normalizeViolationKey(type: string): string {
  return type.toLowerCase().replace(/[^a-z]/g, "")
}

export function violationLabel(type: string, ppeLabels: Map<string, string>): string {
  const key = normalizeViolationKey(type)
  return VIOLATION_LABELS[key] ?? ppeLabels.get(type) ?? type.replace(/[_-]+/g, " ")
}

/** Backend timestamps may be naive UTC; interpret them as UTC instead of local time. */
export function parseTs(timestamp: string): Date {
  const value = String(timestamp ?? "").trim()
  if (!value) return new Date(Number.NaN)
  if (/Z$|[+-]\d{2}:?\d{2}$/.test(value)) return new Date(value)
  return new Date(`${value.replace(" ", "T")}Z`)
}

export function iso(date: Date): string {
  return date.toISOString()
}

export function formatClock(milliseconds: number): string {
  return new Date(milliseconds).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" })
}

export function formatDate(timestamp: string): string {
  return parseTs(timestamp).toLocaleDateString(LOCALE, { day: "2-digit", month: "short", year: "numeric" })
}

export function formatTime(timestamp: string): string {
  return parseTs(timestamp).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

const relativeFormatter = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" })
export function formatRelative(timestamp: string, now: number): string {
  const diffSec = (parseTs(timestamp).getTime() - now) / 1000
  if (!Number.isFinite(diffSec)) return "وقت غير معروف"
  const abs = Math.abs(diffSec)
  if (abs < 45) return "الآن"
  if (abs < 3600) return relativeFormatter.format(Math.round(diffSec / 60), "minute")
  if (abs < 86400) return relativeFormatter.format(Math.round(diffSec / 3600), "hour")
  return relativeFormatter.format(Math.round(diffSec / 86400), "day")
}

/** Mask embedded credentials before rendering a camera source URI. */
export function maskUri(uri?: string | null): string {
  if (!uri) return ""
  return uri
    .replace(/\/\/([^@/]+)@/g, "//•••@")
    .replace(/([?&](?:user(?:name)?|pass(?:word)?|(?:access|refresh|id|auth)[_-]?token|token|(?:client[_-]?)?secret|auth(?:orization)?|bearer|api[_-]?key|session[_-]?id|cookie|credentials?)=)[^&#]*/gi, "$1•••")
}

export function computeCompliance(profile: string | undefined, counts: LiveCounts): number | undefined {
  if (profile === "medical") return undefined
  const persons = counts.person ?? 0
  if (persons <= 0 || counts.hardhat === undefined) return undefined
  return Math.round(Math.min(1, counts.hardhat / persons) * 100)
}

export function liveMetrics(profile: string | undefined, counts: LiveCounts): LiveMetricItem[] {
  if (profile === "medical") {
    return [
      { value: counts.no_mask, label: "بدون كمامة" },
      { value: counts.no_gloves, label: "بدون قفازات" },
      { value: counts.no_goggles, label: "بدون نظارات واقية" },
      { value: counts.no_cap, label: "بدون غطاء رأس" },
      { value: counts.total, label: "إجمالي الكشف" },
    ]
  }
  return [
    { value: counts.person, label: "أشخاص" },
    { value: counts.hardhat, label: "خوذات" },
    { value: counts.vest, label: "سترات" },
  ]
}

/** Normalize current and legacy camera-manager websocket payloads. */
export function normalizeLiveCounts(raw: unknown): LiveCounts | null {
  if (!raw || typeof raw !== "object") return null
  const data = raw as Record<string, unknown>
  if (data.ping) return null
  const numberOrUndefined = (value: unknown): number | undefined => {
    const number = Number(value)
    return Number.isFinite(number) ? number : undefined
  }
  return {
    hardhat: numberOrUndefined(data.hardhat ?? data.hardhat_count),
    vest: numberOrUndefined(data.vest ?? data.vest_count),
    person: numberOrUndefined(data.person ?? data.person_count),
    no_mask: numberOrUndefined(data.no_mask),
    no_gloves: numberOrUndefined(data.no_gloves),
    no_goggles: numberOrUndefined(data.no_goggles),
    no_cap: numberOrUndefined(data.no_cap),
    skin_hits: numberOrUndefined(data.skin_hits),
    total: numberOrUndefined(data.total ?? data.total_detections),
  }
}

export function withParams(url: string, params: Record<string, string | undefined>): string {
  try {
    const isAbsolute = /^[a-z][a-z\d+.-]*:/i.test(url)
    const parsed = new URL(url, window.location.origin)
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") parsed.searchParams.set(key, value)
    }
    return isAbsolute ? parsed.toString() : `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    return url
  }
}

export function tooltipStyle() {
  return {
    borderRadius: 12,
    border: "1px solid var(--border)",
    background: "var(--popover)",
    color: "var(--foreground)",
    fontSize: 12,
    fontWeight: 600,
    boxShadow: "0 8px 24px -6px rgba(15,23,42,0.2)",
    direction: "rtl" as const,
  }
}

export function countFormatter(value: unknown, name?: unknown): [string, string] {
  const count = Array.isArray(value) ? value.length : Number(value ?? 0)
  return [`${Number.isFinite(count) ? count : 0} مخالفة`, name ? String(name) : ""]
}

export function makeLabelFormatter(prefix: string) {
  return (label: ReactNode) => `${prefix} ${label == null ? "" : String(label)}`
}

export function compareViolationsByNewest(a: Violation, b: Violation): number {
  return parseTs(b.timestamp).getTime() - parseTs(a.timestamp).getTime()
}

export function getRangeLabel(range: RangeKey): string {
  return range === "24h" ? "آخر 24 ساعة" : "آخر 7 أيام"
}
