import type { LiveCounts, RuleKey, SiteKind, TabKey, UserRole } from "@/types"

export const LOCALE = "ar-EG-u-nu-latn"
export const ROLE_LABEL: Record<UserRole, string> = {
  admin: "مدير النظام",
  supervisor: "مشرف السلامة",
  viewer: "مشاهد",
}
export const SITE_LABEL: Record<SiteKind, string> = {
  factory: "مصنع",
  construction: "موقع إنشاء",
  workshop: "ورشة صناعية",
  warehouse: "مستودع",
  industrial: "منطقة صناعية",
}
export const RULE_LABEL: Record<RuleKey, string> = {
  helmet: "خوذة أمان",
  vest: "سترة عاكسة",
  gloves: "قفازات عمل",
  boots: "حذاء أمان",
  goggles: "نظارات واقية",
}
export const TAB_TITLES: Record<TabKey, string> = {
  overview: "نظرة عامة",
  live: "المراقبة المباشرة",
  cameras: "إدارة الكاميرات",
  uploads: "تحليل الصور والفيديو",
  violations: "التنبيهات وسجل الأحداث",
  sites: "المصانع والمواقع",
  users: "المستخدمون والأدوار",
}
export const NEGATIVE_LABELS: Record<string, string> = {
  "NO-Hardhat": "بدون خوذة أمان",
  "NO-Safety Vest": "بدون سترة عاكسة",
  "NO-Gloves": "بدون قفازات عمل",
  "NO-Boot": "بدون حذاء أمان",
  "NO-Goggles": "بدون نظارات واقية",
}
const CLASS_LABELS: Record<string, string> = {
  ...NEGATIVE_LABELS,
  Person: "عامل",
  Hardhat: "خوذة أمان",
  "Safety Vest": "سترة عاكسة",
  Gloves: "قفازات عمل",
  "Safety Boots": "حذاء أمان",
  Goggles: "نظارات واقية",
}
export const CHART_COLORS = [
  "var(--chart-gold)",
  "var(--chart-soft)",
  "var(--chart-muted)",
  "var(--chart-neutral)",
  "var(--text-soft)",
]
export function classLabel(value: string): string {
  return CLASS_LABELS[value] ?? "فئة غير مدعومة"
}
export function parseTs(value: string): Date {
  const trimmed = String(value ?? "").trim()
  if (!trimmed) return new Date(NaN)
  return new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(trimmed) ? trimmed : trimmed.replace(" ", "T") + "Z")
}
export function formatDate(value: string): string {
  const date = parseTs(value)
  return Number.isNaN(+date)
    ? "—"
    : date.toLocaleDateString(LOCALE, { day: "numeric", month: "short", year: "numeric" })
}
export function formatTime(value: string): string {
  const date = parseTs(value)
  return Number.isNaN(+date)
    ? "—"
    : date.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" })
}
export function num(value: number | undefined): string {
  return value === undefined ? "—" : value.toLocaleString(LOCALE)
}
export function normalizeLiveCounts(raw: unknown): LiveCounts | null {
  if (!raw || typeof raw !== "object" || "ping" in raw) return null
  const keys: (keyof LiveCounts)[] = [
    "person",
    "hardhat",
    "no_hardhat",
    "vest",
    "no_vest",
    "gloves",
    "no_gloves",
    "boots",
    "no_boot",
    "goggles",
    "no_goggles",
    "total",
  ]
  const record = raw as Record<string, unknown>
  if (!keys.some((key) => typeof record[key] === "number")) return null
  return Object.fromEntries(
    keys.map((key) => [
      key,
      typeof record[key] === "number" && Number.isFinite(record[key]) && record[key] >= 0
        ? Math.floor(record[key])
        : 0,
    ]),
  ) as unknown as LiveCounts
}
