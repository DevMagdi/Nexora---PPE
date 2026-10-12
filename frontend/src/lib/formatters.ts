import type { CameraProfile, LiveCounts, LiveMetricItem, LiveStatus, TabKey, ToneKey } from "@/types"

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
}

export const PIE_COLORS = [
  CHART_HEX.green,
  CHART_HEX.blue,
  CHART_HEX.amber,
  CHART_HEX.purple,
  CHART_HEX.red,
]

export const SECTOR_LABEL: Record<string, string> = {
  construction: "قطاع الإنشاءات",
  medical: "القطاع الطبي",
  both: "إدارة عامة",
}

export const PROFILE_LABEL: Record<string, string> = {
  construction: "إنشاءات",
  medical: "طبي",
}

export const SOURCE_TYPE_SHORT: Record<string, string> = {
  webcam: "كاميرا ويب",
  rtsp: "بث RTSP",
  file: "ملف فيديو",
}

export const ROLE_LABEL: Record<string, string> = {
  admin: "مدير النظام",
  operator: "مشغّل",
  viewer: "مشاهد فقط",
}

export const LIVE_STATUS_LABEL: Record<LiveStatus, string> = {
  idle: "",
  connecting: "جارٍ الاتصال...",
  reconnecting: "إعادة الاتصال...",
  open: "مباشر",
}

export const CORE_KEYWORDS = ["hardhat", "helmet", "vest", "mask", "glove", "cap", "goggle", "boot", "coat"]

export const VIOLATION_LABELS: Record<string, string> = {
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

export const TAB_TITLES: Record<TabKey, string> = {
  overview: "نظرة عامة",
  live: "المراقبة المباشرة",
  cameras: "إدارة الكاميرات",
  violations: "سجل المخالفات",
}

export const TONE_CLASSES: Record<ToneKey, { chip: string; text: string; border: string }> = {
  primary: { chip: "bg-primary-light", text: "text-primary", border: "border-primary/20" },
  info: { chip: "bg-info-light", text: "text-info-foreground", border: "border-info/20" },
  warning: { chip: "bg-warning-light", text: "text-warning-foreground", border: "border-warning/20" },
  destructive: { chip: "bg-destructive-light", text: "text-destructive-foreground", border: "border-destructive/20" },
  success: { chip: "bg-success-light", text: "text-success-foreground", border: "border-success/20" },
}

export function cameraProfile(c: { profile?: string } | null | undefined): CameraProfile {
  return c?.profile === "medical" ? "medical" : "construction"
}

export function isCoreType(type: string): boolean {
  return CORE_KEYWORDS.some((k) => type.toLowerCase().includes(k))
}

export function normalizeViolationKey(type: string): string {
  return type.toLowerCase().replace(/[^a-z]/g, "")
}

export function violationLabel(type: string, ppeLabels: Map<string, string>): string {
  const key = normalizeViolationKey(type)
  return VIOLATION_LABELS[key] ?? ppeLabels.get(type) ?? type.replace(/[_-]+/g, " ")
}

/**
 * الباك بيخزّن utc_now() كـ naive UTC من غير Z.
 * JS بيقرأ "2026-10-11T16:33:00" كـ local، فبنفرض UTC لو مفيش timezone.
 */
export function parseTs(ts: string): Date {
  const s = String(ts ?? "").trim()
  if (!s) return new Date(NaN)
  if (/Z$|[+-]\d{2}:?\d{2}$/.test(s)) return new Date(s)
  return new Date(s.replace(" ", "T") + "Z")
}

export function iso(d: Date): string {
  return d.toISOString()
}

export function formatClock(ms: number): string {
  return new Date(ms).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" })
}

export function formatDate(ts: string): string {
  return parseTs(ts).toLocaleDateString(LOCALE, { day: "2-digit", month: "short", year: "numeric" })
}

export function formatTime(ts: string): string {
  return parseTs(ts).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

const relativeFormatter = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" })
export function formatRelative(ts: string, now: number): string {
  const diffSec = (parseTs(ts).getTime() - now) / 1000
  const abs = Math.abs(diffSec)
  if (abs < 45) return "الآن"
  if (abs < 3600) return relativeFormatter.format(Math.round(diffSec / 60), "minute")
  if (abs < 86400) return relativeFormatter.format(Math.round(diffSec / 3600), "hour")
  return relativeFormatter.format(Math.round(diffSec / 86400), "day")
}

export function maskUri(uri?: string | null): string {
  if (!uri) return ""
  return uri.replace(/\/\/([^@/]+)@/, "//•••@")
}

function n(v: unknown): number | undefined {
  const x = Number(v)
  return Number.isFinite(x) ? x : undefined
}

/** يوحّد payload الـ WS (مفاتيح الباك الحالية + القديمة) */
export function normalizeLiveCounts(raw: unknown): LiveCounts | null {
  if (!raw || typeof raw !== "object") return null
  const d = raw as Record<string, unknown>
  if (d.ping) return null
  return {
    hardhat: n(d.hardhat ?? d.hardhat_count),
    vest: n(d.vest ?? d.vest_count),
    person: n(d.person ?? d.person_count),
    no_mask: n(d.no_mask),
    no_gloves: n(d.no_gloves),
    no_goggles: n(d.no_goggles),
    no_cap: n(d.no_cap),
    skin_hits: n(d.skin_hits),
    total: n(d.total ?? d.total_detections),
  }
}

export function computeCompliance(profile: string | undefined, c: LiveCounts): number | undefined {
  if (profile === "medical") return undefined
  const persons = c.person ?? 0
  if (persons <= 0 || c.hardhat === undefined) return undefined
  return Math.round(Math.min(1, c.hardhat / persons) * 100)
}

export function liveMetrics(profile: string | undefined, c: LiveCounts): LiveMetricItem[] {
  if (profile === "medical") {
    return [
      { value: c.no_mask, label: "بدون كمامة" },
      { value: c.no_gloves, label: "بدون قفازات" },
      { value: c.no_goggles, label: "بدون نظارات واقية" },
      { value: c.no_cap, label: "بدون غطاء رأس" },
      { value: c.total, label: "إجمالي الكشف" },
    ]
  }
  return [
    { value: c.person, label: "أشخاص" },
    { value: c.hardhat, label: "خوذات" },
    { value: c.vest, label: "سترات" },
  ]
}

export function withParams(url: string, params: Record<string, string | undefined>): string {
  try {
    const isAbsolute = /^[a-z][a-z\d+.-]*:/i.test(url)
    const u = new URL(url, window.location.origin)
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") u.searchParams.set(k, v)
    }
    return isAbsolute ? u.toString() : `${u.pathname}${u.search}${u.hash}`
  } catch {
    return url
  }
}
