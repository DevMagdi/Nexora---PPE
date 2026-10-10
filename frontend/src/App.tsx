// frontend/src/App.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import AddCameraForm from "@/components/AddCameraForm"
import ConfirmDialog from "@/components/ConfirmDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  useCameras,
  useDeleteCamera,
  useHealth,
  usePPEClassesMeta,
  useResolveViolation,
  useStartCamera,
  useStopCamera,
  useViolations,
} from "@/hooks/useNexora"
import { getMjpegStreamUrl, getWebSocketUrl, getViolationsExportUrl } from "@/lib/api"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import nexoraLogoWhite from "@/assets/logo/nexora-logo-full-white.svg"
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  Boxes,
  Camera as CameraIcon,
  Cctv,
  CheckCircle2,
  ChevronDown,
  Clock,
  Download,
  Eye,
  HardHat,
  Image as ImageIcon,
  LayoutGrid,
  Loader2,
  Menu,
  Moon,
  MonitorPlay,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Shirt,
  Sparkles,
  Square,
  Sun,
  Trash2,
  Users,
  Wifi,
  WifiOff,
  X,
} from "lucide-react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

/* ─── Types ─── */

type RangeKey = "24h" | "7d"
type TabKey = "overview" | "live" | "cameras" | "violations"
type ToneKey = "primary" | "info" | "warning" | "destructive" | "success"
type LiveStatus = "idle" | "connecting" | "open" | "reconnecting"
type Camera = NonNullable<ReturnType<typeof useCameras>["data"]>[number]
type Violation = NonNullable<ReturnType<typeof useViolations>["data"]>["items"][number]
type ToastState = { id: number; tone: "success" | "error"; text: string }

type LiveCounts = {
  hardhat_count?: number
  vest_count?: number
  person_count?: number
  total_detections?: number
}

/* ─── Constants ─── */

const LOCALE = "ar-EG-u-nu-latn" // عربي بأرقام لاتينية متسقة في كل الواجهة
const HOUR = 3_600_000
const DAY = 24 * HOUR
const VIOLATIONS_FETCH_LIMIT = 200
const TABLE_PAGE_SIZE = 25
const MAX_GRID_PREVIEWS = 4 // أقصى عدد بثوث معاينة متزامنة (المتصفح بيسمح بحوالي 6 اتصالات لكل سيرفر)

const CHART_HEX = {
  green: "var(--chart-green)",
  red: "var(--chart-red)",
  amber: "var(--chart-amber)",
  blue: "var(--chart-blue)",
  purple: "var(--chart-purple)",
}
const PIE_COLORS = [CHART_HEX.green, CHART_HEX.blue, CHART_HEX.amber, CHART_HEX.purple, CHART_HEX.red]

/** مؤقتًا بيقرأ المستخدم من localStorage["nexora-user"] = {"name","role"}؛ بدّله ببيانات تسجيل الدخول لما يجهز */
function getCurrentUser() {
  try {
    const raw = localStorage.getItem("nexora-user")
    const u = raw ? JSON.parse(raw) : null
    if (u?.name) return { name: String(u.name), role: String(u.role ?? "") }
  } catch {
    /* بيانات غير صالحة، نتجاهلها */
  }
  return { name: "مستخدم Nexora", role: "حساب محلي" }
}
const CURRENT_USER = getCurrentUser()

const CORE_KEYWORDS = ["hardhat", "helmet", "vest", "mask"]

/**
 * يحوّل أي صيغة لنوع المخالفة (NO-Hardhat / no_hardhat / NO Hardhat...)
 * لمفتاح موحّد (حروف صغيرة + بدون رموز) عشان المقارنة تبقى موثوقة
 * بغض النظر عن الصيغة اللي راجعة من الـ backend فعليًا.
 */
function normalizeViolationKey(type: string): string {
  return type.toLowerCase().replace(/[^a-z]/g, "")
}

const VIOLATION_LABELS: Record<string, string> = {
  nohardhat: "بدون خوذة",
  nohelmet: "بدون خوذة",
  nosafetyvest: "بدون سترة عاكسة",
  novest: "بدون سترة عاكسة",
  nomask: "بدون كمامة",
  nogloves: "بدون قفازات",
  nogoggles: "بدون نظارات واقية",
  nosafetyboots: "بدون حذاء أمان",
  noboots: "بدون حذاء أمان",
  nolabcoat: "بدون بالطو واقي",
  nocoat: "بدون بالطو واقي",
}

const TAB_TITLES: Record<TabKey, string> = {
  overview: "نظرة عامة",
  live: "المراقبة المباشرة",
  cameras: "إدارة الكاميرات",
  violations: "سجل المخالفات",
}

const TONE_CLASSES: Record<ToneKey, { chip: string; text: string }> = {
  primary: { chip: "bg-primary-light", text: "text-primary" },
  info: { chip: "bg-info-light", text: "text-info-foreground" },
  warning: { chip: "bg-warning-light", text: "text-warning-foreground" },
  destructive: { chip: "bg-destructive-light", text: "text-destructive-foreground" },
  success: { chip: "bg-success-light", text: "text-success-foreground" },
}

/* ─── Helpers ─── */

function isCoreType(type: string) {
  return CORE_KEYWORDS.some((k) => type.toLowerCase().includes(k))
}

/** اسم عربي لنوع المخالفة مع fallback على بيانات الـ API ثم النص الخام */
function violationLabel(type: string, ppeLabels: Map<string, string>) {
  const key = normalizeViolationKey(type)
  return VIOLATION_LABELS[key] ?? ppeLabels.get(type) ?? type.replace(/[_-]+/g, " ")
}

function iso(d: Date) {
  return d.toISOString()
}

function formatClock(ms: number) {
  return new Date(ms).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" })
}

function formatDate(ts: string) {
  return new Date(ts).toLocaleDateString(LOCALE, { day: "2-digit", month: "short", year: "numeric" })
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

const relativeFormatter = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" })
function formatRelative(ts: string, now: number) {
  const diffSec = (new Date(ts).getTime() - now) / 1000
  const abs = Math.abs(diffSec)
  if (abs < 45) return "الآن"
  if (abs < 3600) return relativeFormatter.format(Math.round(diffSec / 60), "minute")
  if (abs < 86400) return relativeFormatter.format(Math.round(diffSec / 3600), "hour")
  return relativeFormatter.format(Math.round(diffSec / 86400), "day")
}

/** يخفي اسم المستخدم وكلمة المرور من روابط RTSP قبل عرضها */
function maskUri(uri?: string | null) {
  if (!uri) return ""
  return uri.replace(/\/\/([^@/]+)@/, "//•••@")
}

/** نسبة الالتزام بالخوذة = الخوذات ÷ الأشخاص (undefined لو مفيش أشخاص أو مفيش بيانات) */
function computeCompliance(c: LiveCounts) {
  const persons = c.person_count ?? 0
  if (persons <= 0 || c.hardhat_count === undefined) return undefined
  return Math.round(Math.min(1, c.hardhat_count / persons) * 100)
}

/** يضيف query params لرابط (مطلق أو نسبي) من غير ما يكسر الـ params الموجودة */
function withParams(url: string, params: Record<string, string | undefined>) {
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

function tooltipStyle() {
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
/** formatters متوافقة مع أنواع recharts v3 (value ممكن تكون undefined، و label هي ReactNode) */
function countFormatter(value: unknown, name?: unknown): [string, string] {
  const n = Array.isArray(value) ? value.length : Number(value ?? 0)
  return [`${Number.isFinite(n) ? n : 0} مخالفة`, name ? String(name) : ""]
}

function makeLabelFormatter(prefix: string) {
  return (label: ReactNode) => `${prefix} ${label == null ? "" : String(label)}`
}

/* ─── Hooks ─── */

/** بيقرأ القيمة الصحيحة من أول render عشان السايدبار ميفتحش غلط على الموبايل */
function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  )
  useEffect(() => {
    const mq = window.matchMedia(query)
    setMatches(mq.matches)
    const onChange = () => setMatches(mq.matches)
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [query])
  return matches
}

/** عداد متحرك بيكمل من آخر قيمة معروضة فعليًا (مش بيقفز لو الهدف اتغير وسط الحركة) */
function useCountUp(target: number | undefined, duration = 700) {
  const [value, setValue] = useState(0)
  const currentRef = useRef(0)
  useEffect(() => {
    if (target === undefined) return
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const start = currentRef.current
    const diff = target - start
    if (diff === 0 || reduceMotion) {
      currentRef.current = target
      setValue(target)
      return
    }
    const t0 = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const progress = Math.min((now - t0) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const next = Math.round(start + diff * eased)
      currentRef.current = next
      setValue(next)
      if (progress < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return target === undefined ? undefined : value
}

/** بيقول لو العنصر ظاهر على الشاشة (لتشغيل معاينات البث الظاهرة فقط) */
function useInView<T extends Element>() {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { rootMargin: "100px" })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return [ref, inView] as const
}

/** يحتفظ بآخر بيانات وصلت عشان الشاشة متعملش flash وقت تحديث الـ query */
function useLatest<T>(value: T | undefined) {
  const ref = useRef<T | undefined>(value)
  if (value !== undefined) ref.current = value
  return ref.current
}
/** الوضع الفاتح هو الأساسي، والداكن اختياري ومتحفوظ في المتصفح */
function useTheme() {
  const [dark, setDark] = useState(() => {
    try {
      return localStorage.getItem("nexora-theme") === "dark"
    } catch {
      return false
    }
  })
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    try {
      localStorage.setItem("nexora-theme", dark ? "dark" : "light")
    } catch {
      /* التخزين غير متاح */
    }
  }, [dark])
  return [dark, setDark] as const
}

/* ─── UI Components ─── */

function LiveDot({ tone = "success", active = true }: { tone?: "success" | "warning" | "destructive"; active?: boolean }) {
  const bg = { success: "bg-success", warning: "bg-warning", destructive: "bg-destructive" }[tone]
  return (
    <span className="relative inline-flex size-2" aria-hidden="true">
      {active && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${bg}`} />}
      <span className={`relative inline-flex size-2 rounded-full ${active ? bg : "bg-muted-foreground/40"}`} />
    </span>
  )
}

function Card({ children, className = "", featured = false }: { children: ReactNode; className?: string; featured?: boolean }) {
  return (
    <div className={`${featured ? "card-featured" : "card-premium border border-border"} text-card-foreground ${className}`}>
      {children}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: number | undefined
  icon: ReactNode
  tone?: ToneKey
  unit?: string
  plus?: boolean
  hint?: ReactNode
  live?: boolean
  featured?: boolean
}

/** كارت إحصائية: الرقم متحرك، و"—" لو مفيش بيانات بدل صفر مضلل */
function StatCard({ label, value, icon, tone = "primary", unit, plus, hint, live, featured }: StatCardProps) {
  const animated = useCountUp(value)
  const t = TONE_CLASSES[tone]
  return (
    <Card featured={featured} className="group relative h-full overflow-hidden p-7">
      <div className="mb-6 flex items-start justify-between">
        <div className={`flex size-12 items-center justify-center rounded-xl ${t.chip} ${t.text}`}>{icon}</div>
        {live !== undefined && <LiveDot tone={tone === "destructive" ? "destructive" : "success"} active={live} />}
      </div>
      <div className={`text-[2.5rem] font-bold leading-none tabular-nums ${featured ? "text-gradient" : "text-foreground"}`}>
        {animated === undefined ? (
          "—"
        ) : (
          <>
            {animated}
            {plus && "+"}
            {unit && <span className="ms-0.5 text-2xl">{unit}</span>}
          </>
        )}
      </div>
      <div className="mt-3 text-sm font-medium text-muted-foreground">{label}</div>
      {hint && <div className="mt-3 truncate text-[11px] font-medium text-muted-foreground">{hint}</div>}
    </Card>
  )
}

/** حلقة نسبة الالتزام: أكبر عنصر في اللوحة، ولونها بيتغير حسب الحالة */
function ComplianceRing({ value, live, hint }: { value: number | undefined; live: boolean; hint: string }) {
  const animated = useCountUp(value)
  const R = 54
  const C = 2 * Math.PI * R
  const v = value ?? 0
  const level = value === undefined ? "none" : v >= 90 ? "good" : v >= 70 ? "warn" : "bad"
  const ringClass = { none: "text-muted-foreground", good: "text-success", warn: "text-warning", bad: "text-destructive" }[level]
  const textClass = { none: "text-muted-foreground", good: "text-success-foreground", warn: "text-warning-foreground", bad: "text-destructive-foreground" }[level]
  const status = { none: "لا يوجد بث", good: "التزام ممتاز", warn: "يحتاج متابعة", bad: "مستوى خطر" }[level]
  return (
    <Card className="flex h-full flex-col items-center justify-center gap-5 p-6 text-center sm:flex-row sm:text-start lg:flex-col lg:text-center xl:flex-row xl:text-start">
      <div className="relative size-44 shrink-0">
        <svg viewBox="0 0 128 128" className="size-full -rotate-90" aria-hidden="true">
          <circle cx="64" cy="64" r={R} fill="none" strokeWidth="10" className="stroke-muted" />
          <circle
            cx="64"
            cy="64"
            r={R}
            fill="none"
            strokeWidth="10"
            strokeLinecap="round"
            stroke="currentColor"
            className={`${ringClass} transition-[stroke-dashoffset] duration-700`}
            strokeDasharray={C}
            strokeDashoffset={C * (1 - v / 100)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center" dir="ltr">
          <span className="text-5xl font-bold tabular-nums">{animated === undefined ? "—" : `${animated}%`}</span>
        </div>
      </div>
      <div className="min-w-0">
        <div className="flex items-center justify-center gap-2 sm:justify-start lg:justify-center xl:justify-start">
          <h3 className="text-sm font-semibold text-muted-foreground">نسبة الالتزام بالخوذة</h3>
          <LiveDot tone="success" active={live} />
        </div>
        <p className={`mt-1.5 text-lg font-bold ${textClass}`}>{status}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </div>
    </Card>
  )
}

function EmptyState({
  title,
  desc,
  action,
  icon,
  compact = false,
}: {
  title: string
  desc?: string
  action?: ReactNode
  icon?: ReactNode
  compact?: boolean
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${
        compact ? "py-10" : "rounded-2xl border border-dashed border-border bg-card py-16"
      }`}
    >
      <div className="relative mb-5 flex size-20 items-center justify-center" aria-hidden="true">
        <span className="absolute inset-0 animate-soft-pulse rounded-full bg-primary/15" />
        <span className="absolute inset-0 rounded-full bg-primary-light" />
        <span className="absolute inset-2.5 rounded-full bg-card ring-1 ring-primary/20" />
        <span className="absolute -end-1 top-1 size-3 animate-soft-float rounded-full bg-primary/30" />
        <span className="absolute -start-1 bottom-2 size-2 animate-soft-float rounded-full bg-primary/40 [animation-delay:1.2s]" />
        <span className="relative">{icon ?? <Sparkles className="size-6 text-primary" />}</span>
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {desc && <p className="mt-2 max-w-xs text-xs leading-relaxed text-muted-foreground">{desc}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

function ErrorState({
  title,
  desc = "تحقق من اتصال الخادم ثم أعد المحاولة.",
  onRetry,
  compact = false,
}: {
  title: string
  desc?: string
  onRetry: () => void
  compact?: boolean
}) {
  return (
    <EmptyState
      compact={compact}
      icon={<WifiOff className="size-6 text-destructive" />}
      title={title}
      desc={desc}
      action={
        <Button type="button" variant="outline" onClick={onRetry} className="gap-2 rounded-xl">
          <RefreshCw className="size-4" /> إعادة المحاولة
        </Button>
      }
    />
  )
}

function SegToggle({
  checked,
  onChange,
  labelOn,
  labelOff,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  labelOn: string
  labelOff: string
}) {
  const base = "relative z-10 rounded-lg px-3.5 py-1.5 transition-colors"
  return (
    <div
      role="group"
      className="relative inline-grid grid-cols-2 rounded-xl border border-border/80 bg-muted/60 p-1 text-xs font-semibold"
    >
      <span
        aria-hidden="true"
        className="absolute bottom-1 start-1 top-1 w-[calc(50%-4px)] rounded-lg border border-border/50 bg-card shadow-md transition-transform duration-200 ease-out"
        style={{ transform: checked ? "translateX(-100%)" : "translateX(0)" }}
      />
      <button
        type="button"
        aria-pressed={!checked}
        onClick={() => onChange(false)}
        className={`${base} ${!checked ? "font-bold text-foreground" : "text-muted-foreground"}`}
      >
        {labelOff}
      </button>
      <button
        type="button"
        aria-pressed={checked}
        onClick={() => onChange(true)}
        className={`${base} ${checked ? "font-bold text-foreground" : "text-muted-foreground"}`}
      >
        {labelOn}
      </button>
    </div>
  )
}

function NavItem({
  icon,
  label,
  active,
  onClick,
  badge,
  hint,
  disabled,
}: {
  icon: ReactNode
  label: string
  active: boolean
  onClick: () => void
  badge?: number
  hint?: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      aria-current={active ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={`group relative flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        active
          ? "bg-primary-light text-primary ring-1 ring-inset ring-primary/25"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      {active && (
        <span
          aria-hidden="true"
          className="absolute end-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-s-full bg-primary"
        />
      )}
      <span
        className={`flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors ${
          active ? "bg-primary text-primary-foreground shadow-sm" : "bg-muted text-muted-foreground group-hover:text-foreground"
        }`}
      >
        {icon}
      </span>
      <span className="flex-1 truncate text-start">{label}</span>
      {hint && <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-bold text-muted-foreground">{hint}</span>}
      {badge !== undefined && badge > 0 && (
        <Badge variant="destructive" className="h-5 min-w-[18px] justify-center px-1.5 text-[11px] font-bold">
          {badge > 99 ? "99+" : badge}
        </Badge>
      )}
    </button>
  )
}

function Toast({ toast, onClose }: { toast: ToastState | null; onClose: () => void }) {
  if (!toast) return null
  const ok = toast.tone === "success"
  return (
    <div role="status" aria-live="polite" className="fixed inset-x-0 bottom-4 z-[60] mx-auto w-fit max-w-[92vw] animate-fade-in-up">
      <div
        className={`glass flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm font-semibold shadow-2xl ring-1 ${
          ok ? "ring-success/40" : "ring-destructive/40"
        }`}
      >
        {ok ? <CheckCircle2 className="size-4 shrink-0 text-success" /> : <AlertTriangle className="size-4 shrink-0 text-destructive" />}
        <span>{toast.text}</span>
        <button type="button" aria-label="إغلاق" onClick={onClose} className="ms-1 rounded-md p-1 text-muted-foreground hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>
    </div>
  )
}

/** رقم متحرك صغير لطبقة البث */
function LiveMetric({ value, label }: { value: number | undefined; label: string }) {
  const animated = useCountUp(value)
  return (
    <div className="rounded-xl bg-white/10 px-3.5 py-2 ring-1 ring-white/15 backdrop-blur-md">
      <div className="text-base font-bold tabular-nums text-white">{animated ?? "—"}</div>
      <div className="mt-0.5 text-white/70">{label}</div>
    </div>
  )
}

const LIVE_STATUS_LABEL: Record<LiveStatus, string> = {
  idle: "",
  connecting: "جارٍ الاتصال...",
  reconnecting: "إعادة الاتصال...",
  open: "مباشر",
}

interface LiveStageProps {
  camera: Camera | null
  counts: LiveCounts
  status: LiveStatus
  compliance: number | undefined
  pending: boolean
  onStart: () => void
  onStop: () => void
  onGoCameras: () => void
}

/**
 * مسرح البث: الـ <img> مفتاحها camera.id فقط، فمش بتتعمل remount مع كل frame.
 * لو البث وقع بيظهر زرار إعادة محاولة بيغيّر الرابط بـ nonce عشان المتصفح يفتح اتصال جديد.
 */
function LiveStage({ camera, counts, status, compliance, pending, onStart, onStop, onGoCameras }: LiveStageProps) {
  const [streamError, setStreamError] = useState(false)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    setStreamError(false)
    setNonce(0)
  }, [camera?.id, camera?.is_running])

  const retry = () => {
    setStreamError(false)
    setNonce((n) => n + 1)
  }

  if (!camera) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-8 text-center">
        <MonitorPlay className="mb-4 size-16 text-muted-foreground/20" />
        <h3 className="mb-2 text-xl font-bold">اختر كاميرا لبدء المراقبة</h3>
        <p className="mb-6 max-w-sm text-sm text-muted-foreground">اختر أحد المصادر من القائمة الجانبية لعرض البث المباشر والتحليل الذكي.</p>
        <Button type="button" variant="outline" onClick={onGoCameras} className="gap-2 rounded-xl">
          <CameraIcon className="size-4" /> إدارة الكاميرات
        </Button>
      </div>
    )
  }

  if (!camera.is_running) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-b from-background to-card p-8 text-center">
        <WifiOff className="mb-4 size-16 text-destructive/20" />
        <h3 className="mb-2 text-xl font-bold">البث متوقف حاليًا</h3>
        <p className="mb-6 max-w-sm text-sm text-muted-foreground">«{camera.name}» لا تعمل الآن. اضغط تشغيل لبدء البث والتحليل اللحظي.</p>
        <button type="button" className="btn-cta" onClick={onStart} disabled={pending}>
          {pending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> جارٍ التشغيل...
            </>
          ) : (
            <>
              <Play className="size-4 fill-current" /> تشغيل البث الآن
            </>
          )}
        </button>
      </div>
    )
  }

  const streamSrc = withParams(getMjpegStreamUrl(camera.id), nonce ? { r: String(nonce) } : {})

  return (
    <>
      {streamError ? (
        <div className="flex h-full w-full flex-col items-center justify-center p-8 text-center">
          <AlertTriangle className="mb-4 size-14 text-warning/60" />
          <h3 className="mb-2 text-lg font-bold text-white">تعذّر الاتصال بالبث</h3>
          <p className="mb-6 max-w-sm text-sm text-white/60">الكاميرا تعمل لكن تدفق الفيديو لم يصل. تحقق من الشبكة أو أعد المحاولة.</p>
          <Button type="button" variant="outline" onClick={retry} className="gap-2 rounded-xl">
            <RefreshCw className="size-4" /> إعادة المحاولة
          </Button>
        </div>
      ) : (
        <img
          key={camera.id}
          src={streamSrc}
          onError={() => setStreamError(true)}
          className="absolute inset-0 z-0 h-full w-full object-contain"
          alt={`البث المباشر من ${camera.name}`}
        />
      )}

      <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-[5] shadow-[inset_0_0_140px_rgba(0,0,0,0.5)]" />

      {/* طبقة علوية */}
      <div className="absolute inset-x-0 top-0 z-10 bg-gradient-to-b from-black/85 via-black/30 to-transparent p-6 pb-14">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2.5 truncate text-lg font-bold text-white drop-shadow-lg">
              <span
                className={`size-2.5 shrink-0 rounded-full ${
                  status === "open" ? "bg-destructive animate-pulse shadow-[0_0_12px_rgba(239,68,68,0.7)]" : "bg-warning"
                }`}
              />
              {camera.name}
            </h2>
            <p className="mt-1.5 text-xs text-white/60">
              المعرّف #{camera.id} · المصدر {camera.source_type}
              {status !== "open" && status !== "idle" && <span className="ms-2 text-warning">{LIVE_STATUS_LABEL[status]}</span>}
            </p>
          </div>
          <Badge
            className={`shrink-0 border-none px-2.5 py-1 text-xs font-bold text-white backdrop-blur ${
              status === "open" ? "bg-red-600/95 live-ring" : "bg-amber-700/95"
            }`}
          >
            {status === "open" ? "مباشر" : LIVE_STATUS_LABEL[status] || "..."}
          </Badge>
        </div>
      </div>

      {/* طبقة سفلية */}
      <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/95 via-black/50 to-transparent p-6 pt-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="grid grid-cols-4 gap-2.5 text-xs">
            <LiveMetric value={counts.person_count} label="أشخاص" />
            <LiveMetric value={counts.hardhat_count} label="خوذات" />
            <LiveMetric value={counts.vest_count} label="سترات" />
            <div className="rounded-xl bg-white/10 px-3.5 py-2 ring-1 ring-white/15 backdrop-blur-md">
              <div
                className={`text-base font-bold tabular-nums ${
                  compliance === undefined
                    ? "text-white"
                    : compliance >= 90
                      ? "text-success"
                      : compliance >= 70
                        ? "text-warning"
                        : "text-destructive"
                }`}
              >
                {compliance === undefined ? "—" : `${compliance}%`}
              </div>
              <div className="mt-0.5 text-white/70">التزام</div>
            </div>
          </div>
          <Button
            type="button"
            size="sm"
            variant="destructive"
            onClick={onStop}
            disabled={pending}
            className="gap-2 rounded-xl shadow-xl shadow-destructive/30"
          >
            {pending ? <Loader2 className="size-3.5 animate-spin" /> : <Square size={14} fill="currentColor" />} إيقاف البث
          </Button>
        </div>
      </div>
    </>
  )
}

interface CameraCardProps {
  camera: Camera
  ppeLabels: Map<string, string>
  allowStream: boolean
  pending: boolean
  deletePending: boolean
  alerts: number
  onToggle: () => void
  onWatch: () => void
  onEdit: () => void
  onDelete: () => void
}

/** كارت كاميرا: بيفتح بث المعاينة فقط لو الكارت ظاهر على الشاشة وضمن حد الاتصالات */
function CameraCard({
  camera,
  ppeLabels,
  allowStream,
  pending,
  deletePending,
  alerts,
  onToggle,
  onWatch,
  onEdit,
  onDelete,
}: CameraCardProps) {
  const [ref, inView] = useInView<HTMLDivElement>()
  const showStream = camera.is_running && allowStream && inView
  const classes = camera.enabled_classes ?? []

  return (
    <div ref={ref} className="h-full">
      <Card className="group flex h-full flex-col overflow-hidden">
        <div className="relative h-44 shrink-0 overflow-hidden bg-black">
          {showStream ? (
            <img
              src={getMjpegStreamUrl(camera.id)}
              loading="lazy"
              className="h-full w-full object-cover opacity-80 transition-all duration-700 group-hover:scale-105 group-hover:opacity-100"
              alt={`معاينة ${camera.name}`}
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center bg-secondary/20 text-muted-foreground">
              {camera.is_running ? <MonitorPlay className="mb-2 size-10 opacity-25" /> : <CameraIcon className="mb-2 size-10 opacity-25" />}
              <span className="text-xs font-medium opacity-60">{camera.is_running ? "تعمل · اضغط للمشاهدة" : "متوقفة"}</span>
            </div>
          )}

          <div className="absolute end-3 top-3 rounded-lg border border-white/10 bg-black/70 px-2 py-1 text-[11px] tabular-nums text-white backdrop-blur-md">
            #{camera.id}
          </div>
          <div
            className={`absolute start-3 top-3 flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold text-white shadow-sm ${
              !camera.is_running ? "bg-slate-600/90" : alerts > 0 ? "bg-red-600/95" : "bg-emerald-700/95"
            }`}
          >
            <span className={`size-1.5 rounded-full bg-white ${camera.is_running ? "animate-pulse" : "opacity-60"}`} />
            {!camera.is_running ? "متوقفة" : alerts > 0 ? `${alerts} تنبيه` : "تعمل"}
          </div>
        </div>

        <div className="flex flex-1 flex-col p-5">
          <div className="mb-3">
            <h3 className="truncate text-base font-bold text-foreground transition-colors group-hover:text-primary">{camera.name}</h3>
            <div
              dir="ltr"
              className="mt-1.5 inline-block max-w-full truncate rounded-lg bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground"
              title="تم إخفاء بيانات الدخول"
            >
              {maskUri(camera.source_uri)}
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-1.5">
            {classes.map((k) => (
              <Badge key={k} variant="outline" className="rounded-md border-border/40 bg-muted/40 text-[11px] font-medium text-foreground/70">
                {ppeLabels.get(k) ?? k}
              </Badge>
            ))}
            {classes.length === 0 && <span className="text-[11px] italic text-muted-foreground">لم يتم تحديد فئات</span>}
          </div>

          <div className="mt-auto flex items-center justify-between gap-2 border-t border-border/40 pt-4">
            <Button
              type="button"
              size="sm"
              variant={camera.is_running ? "destructive" : "default"}
              onClick={onToggle}
              disabled={pending || deletePending}
              className={`flex-1 gap-1.5 rounded-xl text-xs font-bold ${
                !camera.is_running ? "bg-primary/12 text-primary hover:bg-primary hover:text-primary-foreground" : ""
              }`}
            >
              {pending ? (
                <Loader2 className="size-3 animate-spin" />
              ) : camera.is_running ? (
                <Square size={12} fill="currentColor" />
              ) : (
                <Play size={12} fill="currentColor" />
              )}
              {camera.is_running ? "إيقاف" : "تشغيل"}
            </Button>

            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label={`مشاهدة ${camera.name}`}
              onClick={onWatch}
              disabled={deletePending}
              className="shrink-0 rounded-xl text-muted-foreground hover:bg-primary/10 hover:text-primary"
            >
              <MonitorPlay size={16} />
            </Button>

            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label={`تعديل ${camera.name}`}
              onClick={onEdit}
              disabled={deletePending}
              className="shrink-0 rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Pencil size={16} />
            </Button>

            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label={`حذف ${camera.name}`}
              onClick={onDelete}
              disabled={deletePending}
              className="shrink-0 rounded-xl text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              {deletePending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 size={16} />}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

/* ─── Main App Component ─── */

export default function App() {
  const isMobile = useMediaQuery("(max-width: 1023.98px)")
  const [dark, setDark] = useTheme()

  const { data: health, isLoading: healthLoading, isError: healthError, refetch: refetchHealth } = useHealth()
  const { data: cameras, isLoading: camerasLoading, isError: camerasError, refetch: refetchCameras } = useCameras()
  const { data: ppeMeta } = usePPEClassesMeta()

  const startMut = useStartCamera()
  const stopMut = useStopCamera()
  const deleteMut = useDeleteCamera()
  const resolveMut = useResolveViolation()

  const [tab, setTab] = useState<TabKey>("overview")
  const [range, setRange] = useState<RangeKey>("24h")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null)
  const [counts, setCounts] = useState<LiveCounts>({})
  const [liveStatus, setLiveStatus] = useState<LiveStatus>("idle")
  const [frameUrl, setFrameUrl] = useState<string | null>(null)
  const [showAllTypes, setShowAllTypes] = useState(false)
  const [cameraSearch, setCameraSearch] = useState("")
  const [typeInput, setTypeInput] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [camFilter, setCamFilter] = useState<number | "all">("all")
  const [page, setPage] = useState(1)
  const [addOpen, setAddOpen] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null)

  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null)

  const [bellOpen, setBellOpen] = useState(false)
  const [seenCount, setSeenCount] = useState<number | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [now, setNow] = useState(() => Date.now())

  /* ساعة حية، والنافذة الزمنية بتتحدث معاها */
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])

  /* النافذة الزمنية مُقرّبة لأقرب ساعة (يومي) أو يوم (أسبوعي) عشان الـ buckets تبقى منتظمة */
  const windowEnd = Math.ceil(now / 60_000) * 60_000
  const { from, to } = useMemo(() => {
    const end = new Date(windowEnd)
    if (range === "24h") {
      end.setMinutes(0, 0, 0)
      end.setTime(end.getTime() + HOUR)
    } else {
      end.setHours(0, 0, 0, 0)
      end.setTime(end.getTime() + DAY)
    }
    return { from: new Date(end.getTime() - (range === "24h" ? DAY : 7 * DAY)), to: end }
  }, [range, windowEnd])
  const rangeLabel = range === "24h" ? "آخر 24 ساعة" : "آخر 7 أيام"

  /* Toast بيختفي لوحده */
  const notify = useCallback((tone: ToastState["tone"], text: string) => setToast({ id: Date.now(), tone, text }), [])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(t)
  }, [toast])

  /* Debounce لفلتر النوع، وإعادة الصفحة للأول عند تغيير أي فلتر */
  useEffect(() => {
    const t = setTimeout(() => setTypeFilter(typeInput.trim()), 350)
    return () => clearTimeout(t)
  }, [typeInput])
  useEffect(() => {
    setPage(1)
  }, [typeFilter, camFilter, showAllTypes, range])

  /* ─── الكاميرات ─── */
  const ppeLabels = useMemo(
    () => new Map<string, string>((ppeMeta?.items ?? []).map((it) => [it.key, it.label_ar] as const)),
    [ppeMeta],
  )
  const cameraList = useMemo(() => cameras ?? [], [cameras])
  const cameraName = useCallback(
    (id: number) => cameraList.find((c) => c.id === id)?.name ?? `كاميرا #${id}`,
    [cameraList],
  )
  const totalCams = cameraList.length
  const runningCams = useMemo(() => cameraList.filter((c) => c.is_running), [cameraList])
  const runningCount = runningCams.length

  /* اختيار تلقائي لأول كاميرا شغالة عشان النظرة العامة تعرض أرقام لحظية من أول ثانية */
  useEffect(() => {
    if (selectedCameraId !== null || cameraList.length === 0) return
    setSelectedCameraId((cameraList.find((c) => c.is_running) ?? cameraList[0]).id)
  }, [cameraList, selectedCameraId])

  /* لو الكاميرا المختارة اتحذفت/اختفت: نختار بديل تلقائيًا */
  useEffect(() => {
    if (selectedCameraId === null) return
    if (cameraList.length === 0) {
      setSelectedCameraId(null)
      return
    }
    if (cameraList.some((c) => c.id === selectedCameraId)) return
    setSelectedCameraId((cameraList.find((c) => c.is_running) ?? cameraList[0]).id)
  }, [cameraList, selectedCameraId])

  const selectedCamera = useMemo(() => cameraList.find((c) => c.id === selectedCameraId) ?? null, [cameraList, selectedCameraId])

  const filteredCams = useMemo(() => {
    const q = cameraSearch.trim().toLowerCase()
    if (!q) return cameraList
    return cameraList.filter((c) => c.name.toLowerCase().includes(q) || String(c.id).includes(q))
  }, [cameraList, cameraSearch])

  /* التحميل خاص بكل كاميرا لوحدها، مش بيقفل كل الأزرار */
  const togglingCamId: number | null =
    startMut.isPending ? (startMut.variables as number) : stopMut.isPending ? (stopMut.variables as number) : null

  const deletingCamId: number | null = deleteMut.isPending ? (deleteMut.variables as number) : null
  const resolvingViolationId: number | null = resolveMut.isPending ? (resolveMut.variables as number) : null

  const toggleCamera = useCallback(
    (c: Camera) => {
      const mut = c.is_running ? stopMut : startMut
      const verb = c.is_running ? "إيقاف" : "تشغيل"
      mut.mutate(c.id, {
        onSuccess: () => notify("success", `تم ${verb} «${c.name}» بنجاح`),
        onError: () => notify("error", `تعذّر ${verb} «${c.name}». تحقق من مصدر الفيديو.`),
      })
    },
    [startMut, stopMut, notify],
  )

  const selectCam = useCallback(
    (id: number) => {
      setSelectedCameraId(id)
      setTab("live")
      if (isMobile) setSidebarOpen(false)
    },
    [isMobile],
  )

  const openEdit = useCallback((c: Camera) => {
    setEditingCamera(c)
    setEditOpen(true)
  }, [])

  const askDelete = useCallback((c: Camera) => {
    setDeleteTarget(c)
    setDeleteOpen(true)
  }, [])

  const confirmDelete = useCallback(() => {
    if (!deleteTarget) return
    const c = deleteTarget
    deleteMut.mutate(c.id, {
      onSuccess: () => {
        setDeleteOpen(false)
        setDeleteTarget(null)
        if (selectedCameraId === c.id) setSelectedCameraId(null)
        notify("success", `تم حذف «${c.name}»`)
      },
      onError: () => notify("error", `تعذّر حذف «${c.name}»`),
    })
  }, [deleteMut, deleteTarget, notify, selectedCameraId])

  const resolveViolation = useCallback(
    (v: Violation) => {
      resolveMut.mutate(v.id, {
        onSuccess: () => notify("success", "تم تعليم المخالفة كمعالجة"),
        onError: () => notify("error", "تعذّر تعليم المخالفة كمعالجة"),
      })
    },
    [resolveMut, notify],
  )

  /* ─── المخالفات ─── */
  const baseParams = useMemo(() => ({ page_size: VIOLATIONS_FETCH_LIMIT, from: iso(from), to: iso(to) }), [from, to])
  const tableParams = useMemo(
    () => ({
      ...baseParams,
      ...(camFilter !== "all" ? { camera_id: camFilter } : {}),
      ...(typeFilter ? { violation_type: typeFilter } : {}),
    }),
    [baseParams, camFilter, typeFilter],
  )

  const {
    data: overviewData,
    //isLoading: overviewLoading,
    isError: overviewError,
    refetch: refetchOverview,
  } = useViolations(baseParams)

  const {
    data: violationsData,
    isLoading: loadingV,
    isError: violationsError,
    refetch: refetchViolations,
  } = useViolations(tableParams)

  const byNewest = (a: Violation, b: Violation) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()

  /* مصدر واحد لكل أرقام النظرة العامة (غير متأثر بفلاتر تاب المخالفات) */
  const overviewRaw = useLatest(overviewData)
  const overviewList = useMemo(() => [...(overviewRaw?.items ?? [])].sort(byNewest), [overviewRaw])
  const coreCount = useMemo(() => overviewList.filter((v) => isCoreType(v.violation_type)).length, [overviewList])
  const overviewCapped = overviewList.length >= VIOLATIONS_FETCH_LIMIT

  /* بيانات الجدول مع pagination محلي */
  const violationsRaw = useLatest(violationsData)
  const filteredList = useMemo(
    () => (violationsRaw?.items ?? []).filter((v) => showAllTypes || isCoreType(v.violation_type)).sort(byNewest),
    [violationsRaw, showAllTypes],
  )
  const pageCount = Math.max(1, Math.ceil(filteredList.length / TABLE_PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const pageItems = filteredList.slice((safePage - 1) * TABLE_PAGE_SIZE, safePage * TABLE_PAGE_SIZE)

  /* أنواع المخالفات المعروفة لقائمة الفلتر */
  const knownTypes = useMemo(() => {
    const s = new Set<string>()
    for (const v of overviewList) s.add(v.violation_type)
    for (const v of violationsRaw?.items ?? []) s.add(v.violation_type)
    return [...s].sort()
  }, [overviewList, violationsRaw])

  /* التصدير مطابق للفلاتر الظاهرة على الشاشة */
  const exportUrl = withParams(getViolationsExportUrl(camFilter === "all" ? undefined : camFilter), {
    from: iso(from),
    to: iso(to),
    violation_type: typeFilter || undefined,
  })

  /* ─── الرسوم البيانية: بالساعة لليوم، وباليوم للأسبوع ─── */
  const series = useMemo(() => {
    const buckets = range === "24h" ? 24 : 7
    const size = range === "24h" ? HOUR : DAY
    const start = from.getTime()
    const arr = Array.from({ length: buckets }, (_, i) => {
      const d = new Date(start + i * size)
      const label =
        range === "24h"
          ? d.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", hour12: false })
          : d.toLocaleDateString(LOCALE, { weekday: "short" })
      return { label, count: 0 }
    })
    for (const v of overviewList) {
      const idx = Math.floor((new Date(v.timestamp).getTime() - start) / size)
      if (idx >= 0 && idx < buckets) arr[idx].count++
    }
    return arr
  }, [overviewList, from, range])

  const pieData = useMemo(() => {
    const m = new Map<string, number>()
    for (const v of overviewList) m.set(v.violation_type, (m.get(v.violation_type) ?? 0) + 1)
    return [...m.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([type, value]) => ({ name: violationLabel(type, ppeLabels), value }))
  }, [overviewList, ppeLabels])

  /* ─── WebSocket مع إعادة اتصال تلقائية وتصفير الأرقام عند تغيير الكاميرا ─── */
  useEffect(() => {
    setCounts({})
    if (!selectedCamera?.is_running) {
      setLiveStatus("idle")
      return
    }
    const camId = selectedCamera.id
    let ws: WebSocket | null = null
    let timer = 0
    let attempts = 0
    let disposed = false

    const connect = () => {
      setLiveStatus(attempts ? "reconnecting" : "connecting")
      ws = new WebSocket(getWebSocketUrl(camId))
      ws.onopen = () => {
        attempts = 0
        setLiveStatus("open")
      }
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data)
          if (typeof d?.person_count === "number" || typeof d?.hardhat_count === "number") setCounts(d)
        } catch {
          /* رسالة غير صالحة، نتجاهلها */
        }
      }
      ws.onerror = () => ws?.close()
      ws.onclose = () => {
        if (disposed) return
        attempts++
        timer = window.setTimeout(connect, Math.min(1000 * 2 ** attempts, 15_000))
      }
    }
    connect()
    return () => {
      disposed = true
      clearTimeout(timer)
      ws?.close()
    }
  }, [selectedCamera?.id, selectedCamera?.is_running])

  const compliance = selectedCamera?.is_running ? computeCompliance(counts) : undefined
  const liveWorkers = selectedCamera?.is_running ? counts.person_count : undefined
  const camPending = selectedCamera !== null && togglingCamId === selectedCamera.id

  /* ─── الجرس: يعدّ الجديد فقط منذ آخر مرة اتفتح ─── */
  useEffect(() => {
    setSeenCount(null)
  }, [range])
  useEffect(() => {
    if (seenCount === null && overviewData) setSeenCount(overviewData.items.length)
  }, [overviewData, seenCount])

  const unseen = seenCount === null ? 0 : Math.max(0, overviewList.length - seenCount)
  const toggleBell = () => {
    setBellOpen((o) => !o)
    setSeenCount(overviewList.length)
  }

  /* Escape يقفل السايدبار والجرس */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSidebarOpen(false)
        setBellOpen(false)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  /* مفيش dialog فاضي: بيفتح بس لو فيه صورة */
  const openFrame = (url?: string | null) => {
    if (url) setFrameUrl(url)
  }

  const navItems: { id: TabKey; icon: ReactNode; badge?: number }[] = [
    { id: "overview", icon: <LayoutGrid className="size-4" /> },
    { id: "live", icon: <MonitorPlay className="size-4" /> },
    { id: "cameras", icon: <CameraIcon className="size-4" /> },
    { id: "violations", icon: <ShieldAlert className="size-4" />, badge: unseen },
  ]

  const sidebarHidden = isMobile && !sidebarOpen
  const serverOk = Boolean(health?.model_loaded) && !healthError

  /* ترتيب الكاميرات في تاب الإدارة: الشغالة أولًا، وأول 4 منها بس بيفتحوا بث معاينة */
  const orderedCams = useMemo(() => [...cameraList].sort((a, b) => Number(b.is_running) - Number(a.is_running)), [cameraList])
  const previewAllowed = useMemo(() => {
    const ids = new Set<number>()
    for (const c of orderedCams) {
      if (c.is_running && ids.size < MAX_GRID_PREVIEWS) ids.add(c.id)
    }
    return ids
  }, [orderedCams])

  /* تنبيهات آخر ساعة لكل كاميرا: بتحدد حالة "تنبيه" على كارت الكاميرا */
  const alertsByCam = useMemo(() => {
    const m = new Map<number, number>()
    for (const v of overviewList) {
      if (isCoreType(v.violation_type) && now - new Date(v.timestamp).getTime() < HOUR) {
        m.set(v.camera_id, (m.get(v.camera_id) ?? 0) + 1)
      }
    }
    return m
  }, [overviewList, now])
  const hourAlerts = useMemo(() => [...alertsByCam.values()].reduce((a, b) => a + b, 0), [alertsByCam])

  const headline =
    compliance === undefined
      ? "شغّل كاميرا لبدء قياس الالتزام"
      : compliance >= 90
        ? "الموقع ملتزم بمعدات الوقاية"
        : compliance >= 70
          ? "الالتزام يحتاج متابعة"
          : "الالتزام منخفض، تدخّل الآن"

  const crumbs = tab === "live" && selectedCamera ? [TAB_TITLES.live, selectedCamera.name] : [TAB_TITLES[tab]]

  return (
    <div className="flex min-h-dvh w-full bg-background text-foreground" dir="rtl" lang="ar">
      {/* ─── Sidebar ─── */}
      <aside
        id="app-sidebar"
        aria-label="التنقل الرئيسي"
        {...(sidebarHidden ? ({ inert: "" } as object) : {})}
        className={`fixed right-0 top-0 z-50 flex h-dvh w-[280px] shrink-0 flex-col border-l border-sidebar-border bg-sidebar transition-transform duration-300 lg:sticky ${
          sidebarHidden ? "translate-x-full" : "translate-x-0 shadow-2xl lg:shadow-none"
        }`}
      >
        <div className="relative flex h-16 shrink-0 items-center justify-center border-b border-sidebar-border bg-gradient-to-b from-primary-light via-primary-light/40 to-transparent">
          <img src={dark ? nexoraLogoWhite : nexoraLogoColor} alt="Nexora" className="h-9 w-auto max-w-[168px] object-contain" />
          {isMobile && (
            <button
              type="button"
              aria-label="إغلاق القائمة"
              onClick={() => setSidebarOpen(false)}
              className="absolute left-3 top-3 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          )}
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto p-4">
          <div className="space-y-1.5">
            <p className="mb-2 px-2.5 text-xs font-semibold text-muted-foreground">القائمة الرئيسية</p>
            {navItems.map((item) => (
              <NavItem
                key={item.id}
                icon={item.icon}
                label={TAB_TITLES[item.id]}
                active={tab === item.id}
                badge={item.badge}
                onClick={() => {
                  setTab(item.id)
                  if (isMobile) setSidebarOpen(false)
                }}
              />
            ))}
          </div>
          <div className="space-y-1.5 border-t border-border/40 pt-5">
            <p className="mb-2 px-2.5 text-xs font-semibold text-muted-foreground">النظام</p>
            <NavItem icon={<Settings className="size-4" />} label="الإعدادات" active={false} hint="قريبًا" disabled onClick={() => {}} />
          </div>
        </nav>

        <div className="shrink-0 border-t border-sidebar-border bg-muted/50 p-4">
          <div className="mb-3.5 flex items-center justify-between text-xs">
            <span className="font-semibold text-muted-foreground">حالة الخادم</span>
            {healthLoading ? (
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> جارٍ الفحص...
              </span>
            ) : healthError ? (
              <button type="button" onClick={() => refetchHealth()} className="flex items-center gap-1.5 font-bold text-destructive-foreground">
                <WifiOff className="size-3.5" /> غير متصل
              </button>
            ) : (
              <span className={`flex items-center gap-1.5 font-bold ${serverOk ? "text-success-foreground" : "text-destructive-foreground"}`}>
                {serverOk ? <Wifi className="size-3.5" /> : <WifiOff className="size-3.5" />}
                {serverOk ? "متصل" : "غير متصل"}
              </span>
            )}
          </div>

          {health && (
            <div className="space-y-2 text-[11px] text-muted-foreground">
              <div className="flex justify-between">
                <span>موديل الذكاء الاصطناعي</span>
                <span className={`font-semibold ${serverOk ? "text-foreground" : "text-destructive-foreground"}`}>{serverOk ? "يعمل" : "متوقف"}</span>
              </div>
              <div className="flex justify-between">
                <span>الكاميرات المُسجّلة</span>
                <span className="font-semibold tabular-nums text-foreground">{totalCams}</span>
              </div>
              <div className="flex justify-between">
                <span>تعمل الآن</span>
                <span className="font-bold tabular-nums text-primary">{runningCount}</span>
              </div>
            </div>
          )}
        </div>

        <div className="shrink-0 border-t border-sidebar-border p-4">
          <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-2.5 ring-1 ring-border">
            <div className="relative shrink-0" aria-hidden="true">
              <div className="flex size-10 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                {CURRENT_USER.name.charAt(0)}
              </div>
              <span className="absolute -bottom-0.5 -end-0.5 size-3 rounded-full bg-success ring-2 ring-card" />
            </div>
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-semibold">{CURRENT_USER.name}</div>
              <div className="mt-0.5 truncate text-xs text-muted-foreground">{CURRENT_USER.role}</div>
            </div>
          </div>
        </div>
      </aside>

      {isMobile && sidebarOpen && (
        <button
          type="button"
          aria-label="إغلاق القائمة"
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ─── Main Content ─── */}
      <main className="flex h-dvh min-w-0 flex-1 flex-col overflow-hidden">
        <header className="glass z-30 flex h-16 shrink-0 items-center justify-between gap-3 px-4 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            {isMobile && (
              <button
                type="button"
                aria-label="فتح القائمة"
                aria-expanded={sidebarOpen}
                aria-controls="app-sidebar"
                onClick={() => setSidebarOpen(true)}
                className="-me-1 rounded-xl p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Menu className="size-5" />
              </button>
            )}
            <div className="min-w-0">
              <nav aria-label="مسار التنقل" className="flex items-center gap-1.5 truncate text-[11px] text-muted-foreground">
                <span>Nexora</span>
                {crumbs.map((c) => (
                  <span key={c} className="flex items-center gap-1.5">
                    <span aria-hidden="true">/</span>
                    {c}
                  </span>
                ))}
              </nav>
              <h1 className="truncate text-lg font-bold lg:text-xl">{TAB_TITLES[tab]}</h1>
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-4">
            <SegToggle checked={range === "7d"} onChange={(v) => setRange(v ? "7d" : "24h")} labelOn="7 أيام" labelOff="اليوم" />

            <div className="hidden h-6 w-px bg-border/60 md:block" />

            <div className="hidden items-center gap-2 text-sm tabular-nums text-muted-foreground sm:flex">
              <Clock className="size-3.5 opacity-70" />
              <time dateTime={new Date(now).toISOString()}>{formatClock(now)}</time>
            </div>

            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label={dark ? "التبديل إلى الوضع الفاتح" : "التبديل إلى الوضع الداكن"}
              onClick={() => setDark((d) => !d)}
              className="rounded-xl hover:bg-muted"
            >
              {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>

            <div className="relative">
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label={`التنبيهات${unseen ? ` (${unseen} جديد)` : ""}`}
                aria-expanded={bellOpen}
                onClick={toggleBell}
                className="relative rounded-xl hover:bg-muted"
              >
                <Bell className="size-4" />
                {unseen > 0 && <span className="absolute right-2 top-2 size-2 animate-pulse rounded-full bg-destructive ring-2 ring-background" />}
              </Button>

              {bellOpen && (
                <>
                  <button type="button" aria-label="إغلاق التنبيهات" className="fixed inset-0 z-40 cursor-default" onClick={() => setBellOpen(false)} />
                  <div className="card-premium absolute left-0 top-12 z-50 w-80 max-w-[90vw] animate-fade-in overflow-hidden rounded-2xl border border-border/60 p-2">
                    <p className="px-3 py-2 text-xs font-bold text-muted-foreground">آخر التنبيهات</p>

                    {overviewError && !overviewRaw ? (
                      <div className="px-3 pb-3">
                        <ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={() => refetchOverview()} />
                      </div>
                    ) : overviewList.length === 0 ? (
                      <p className="px-3 pb-3 text-sm text-muted-foreground">لا توجد تنبيهات في {rangeLabel}.</p>
                    ) : (
                      overviewList.slice(0, 5).map((v) => (
                        <button
                          key={v.id}
                          type="button"
                          onClick={() => {
                            setBellOpen(false)
                            openFrame(v.frame_url)
                          }}
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-start transition-colors hover:bg-muted/40"
                        >
                          <span className="size-2 shrink-0 rounded-full bg-destructive" />
                          <span className="flex-1 truncate text-sm font-semibold">{violationLabel(v.violation_type, ppeLabels)}</span>
                          <span className="shrink-0 text-[11px] text-muted-foreground">{formatRelative(v.timestamp, now)}</span>
                        </button>
                      ))
                    )}

                    <button
                      type="button"
                      onClick={() => {
                        setBellOpen(false)
                        setTab("violations")
                      }}
                      className="mt-1 w-full rounded-xl px-3 py-2 text-center text-xs font-bold text-primary hover:bg-primary/10"
                    >
                      عرض السجل الكامل
                    </button>
                  </div>
                </>
              )}
            </div>

            <div className="flex size-9 items-center justify-center rounded-full bg-primary-light text-xs font-bold text-primary" aria-hidden="true">
              {CURRENT_USER.name.charAt(0)}
            </div>
          </div>
        </header>

        <div key={tab} className="flex-1 animate-page-in overflow-y-auto p-5 lg:p-10">
          {/* ===================== OVERVIEW ===================== */}
          {tab === "overview" && (
            <div className="mx-auto max-w-7xl space-y-12">
              <div>
                <h2 className="text-3xl font-bold leading-tight">{headline}</h2>
                <p className="mt-2 text-sm text-muted-foreground">ملخص الالتزام والتنبيهات خلال {rangeLabel}</p>
              </div>

              <div className="stagger grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
                <div className="lg:col-span-4">
                  <ComplianceRing
                    value={compliance}
                    live={liveStatus === "open"}
                    hint={selectedCamera?.is_running ? `لحظيًا من «${selectedCamera.name}»` : "شغّل كاميرا لعرض النسبة اللحظية"}
                  />
                </div>
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:col-span-8 lg:gap-8">
                  <StatCard
                    label="عمال تحت المراقبة الآن"
                    value={liveWorkers}
                    icon={<Users className="size-5 stroke-[2.5]" />}
                    tone="info"
                    live={liveStatus === "open"}
                    hint={selectedCamera?.is_running ? `${counts.hardhat_count ?? 0} خوذة · ${counts.vest_count ?? 0} سترة` : "لا يوجد بث نشط"}
                  />
                  <StatCard
                    label={`مخالفات ${rangeLabel}`}
                    value={overviewRaw ? overviewList.length : undefined}
                    plus={overviewCapped}
                    icon={<ShieldAlert className="size-5 stroke-[2.5]" />}
                    tone="warning"
                    hint={overviewRaw ? `${coreCount} منها تخص معدات الوقاية الأساسية` : "—"}
                  />
                  <StatCard
                    label="كاميرات تعمل الآن"
                    value={camerasLoading && cameraList.length === 0 ? undefined : runningCount}
                    icon={<Cctv className="size-5 stroke-[2.5]" />}
                    tone="primary"
                    hint={`من ${totalCams} كاميرا مُسجّلة`}
                  />
                  <StatCard
                    label="تنبيهات آخر ساعة"
                    value={overviewRaw ? hourAlerts : undefined}
                    icon={<AlertTriangle className="size-5 stroke-[2.5]" />}
                    tone="destructive"
                    hint={overviewRaw ? (alertsByCam.size > 0 ? `على ${alertsByCam.size} كاميرا` : "لا توجد تنبيهات نشطة") : "—"}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
                <Card className="flex h-[420px] flex-col p-7 lg:col-span-2">
                  <div className="mb-6 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="h-7 w-1.5 rounded-full bg-primary" />
                      <h3 className="text-base font-semibold">المخالفات عبر الوقت</h3>
                    </div>
                    <SegToggle checked={range === "7d"} onChange={(v) => setRange(v ? "7d" : "24h")} labelOn="أسبوعي" labelOff="يومي" />
                  </div>
                  <div className="min-h-0 w-full flex-1" dir="ltr">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={series} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                        <defs>
                          <linearGradient id="violationsFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={CHART_HEX.green} stopOpacity={0.3} />
                            <stop offset="95%" stopColor={CHART_HEX.green} stopOpacity={0.02} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 4" stroke="var(--chart-grid)" vertical={false} />
                        <XAxis
                          dataKey="label"
                          tickLine={false}
                          axisLine={false}
                          stroke="var(--chart-axis)"
                          fontSize={11}
                          interval="preserveStartEnd"
                          minTickGap={28}
                        />
                        <YAxis allowDecimals={false} tickLine={false} axisLine={false} stroke="var(--chart-axis)" fontSize={11} />
                        <Tooltip
                          contentStyle={tooltipStyle()}
                          cursor={{ stroke: "var(--chart-axis)" }}
                          formatter={countFormatter}
                          labelFormatter={makeLabelFormatter(range === "24h" ? "الساعة" : "يوم")}
                        />
                        <Area type="monotone" dataKey="count" stroke={CHART_HEX.green} strokeWidth={2.5} fill="url(#violationsFill)" animationDuration={1000} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <Card className="relative flex h-[420px] flex-col overflow-hidden p-7">
                  <div className="relative z-10 mb-4 flex items-center gap-3">
                    <div className="h-7 w-1.5 rounded-full bg-warning" />
                    <h3 className="text-base font-semibold">توزيع أنواع المخالفات</h3>
                  </div>

                  {pieData.length === 0 ? (
                    <div className="relative z-10 flex flex-1 items-center justify-center">
                      {overviewError && !overviewRaw ? (
                        <ErrorState compact title="تعذّر تحميل بيانات المخالفات" onRetry={() => refetchOverview()} />
                      ) : (
                        <EmptyState
                          compact
                          icon={<ShieldCheck className="size-6 text-success" />}
                          title="الموقع ملتزم"
                          desc={`لم يُسجَّل أي انتهاك في ${rangeLabel}. استمر على هذا المستوى.`}
                        />
                      )}
                    </div>
                  ) : (
                    <>
                      <div className="relative z-10 min-h-0 flex-1">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={pieData}
                              cx="50%"
                              cy="50%"
                              innerRadius={58}
                              outerRadius={82}
                              paddingAngle={4}
                              dataKey="value"
                              cornerRadius={8}
                              animationDuration={900}
                              stroke="none"
                            >
                              {pieData.map((_, i) => (
                                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip contentStyle={tooltipStyle()} formatter={countFormatter} />
                          </PieChart>
                        </ResponsiveContainer>
                        <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
                          <div className="text-3xl font-bold tabular-nums">
                            {overviewList.length}
                            {overviewCapped && "+"}
                          </div>
                          <div className="mt-0.5 text-[11px] font-bold text-muted-foreground">إجمالي الحالات</div>
                        </div>
                      </div>
                      <div className="relative z-10 mt-3 space-y-2 border-t border-border/40 pt-4">
                        {pieData.map((item, i) => (
                          <div key={item.name} className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2.5">
                              <span className="size-2.5 rounded-md" style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />
                              <span className="font-medium text-muted-foreground">{item.name}</span>
                            </div>
                            <span className="rounded-md bg-muted/60 px-2 py-0.5 font-bold tabular-nums">{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </Card>
              </div>

              <Card className="overflow-hidden">
                <div className="flex items-center justify-between border-b border-border/40 bg-card/80 p-5 pb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="rounded-lg bg-destructive/15 p-1.5">
                      <ShieldAlert className="size-4 text-destructive" />
                    </div>
                    <h3 className="text-sm font-bold">آخر التنبيهات المسجلة</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTab("violations")}
                    className="flex items-center gap-1 text-[11px] font-bold text-primary underline-offset-2 hover:underline"
                  >
                    عرض السجل الكامل <ArrowLeft className="size-3" />
                  </button>
                </div>

                <div className="max-h-[380px] divide-y divide-border/70 overflow-y-auto">
                  {overviewError && !overviewRaw ? (
                    <div className="p-4">
                      <ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={() => refetchOverview()} />
                    </div>
                  ) : overviewList.length === 0 ? (
                    <EmptyState
                      compact
                      icon={<ShieldCheck className="size-6 text-success" />}
                      title="كل شيء على ما يرام"
                      desc={`لم يرصد النظام أي مخالفات في ${rangeLabel}.`}
                    />
                  ) : (
                    overviewList.slice(0, 6).map((v) => (
                      <button
                        key={v.id}
                        type="button"
                        onClick={() => openFrame(v.frame_url)}
                        disabled={!v.frame_url}
                        className="group flex w-full items-center gap-4 p-4 text-start transition-colors hover:bg-muted/25 disabled:cursor-default disabled:hover:bg-transparent"
                      >
                        {v.frame_url ? (
                          <img
                            src={v.frame_url}
                            loading="lazy"
                            alt={`لقطة ${violationLabel(v.violation_type, ppeLabels)}`}
                            className="size-14 shrink-0 rounded-xl border border-border/50 object-cover shadow-md transition-transform duration-300 group-hover:scale-105"
                          />
                        ) : (
                          <div className="flex size-14 shrink-0 items-center justify-center rounded-xl border border-border/50 bg-secondary text-muted-foreground">
                            <ImageIcon className="size-5 opacity-50" />
                          </div>
                        )}
                        <div className="min-w-0 flex-1 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant={isCoreType(v.violation_type) ? "destructive" : "secondary"} className="rounded-md px-2 py-0.5 text-[11px] font-bold">
                              {violationLabel(v.violation_type, ppeLabels)}
                            </Badge>
                            <span className="text-[11px] text-muted-foreground">{formatRelative(v.timestamp, now)}</span>
                          </div>
                          <div className="flex items-center gap-2 text-xs">
                            <span className="truncate font-medium text-foreground/85">{cameraName(v.camera_id)}</span>
                            <span className="text-[11px] text-muted-foreground">
                              ثقة الكشف <strong className="tabular-nums text-foreground">{Math.round(v.confidence * 100)}%</strong>
                            </span>
                          </div>
                        </div>
                        {v.frame_url && (
                          <ArrowLeft className="size-4 text-muted-foreground/25 transition-all duration-300 group-hover:-translate-x-1 group-hover:text-primary" />
                        )}
                      </button>
                    ))
                  )}
                </div>
              </Card>
            </div>
          )}

          {/* ===================== LIVE ===================== */}
          {tab === "live" && (
            <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 lg:h-[calc(100dvh-8rem)] lg:grid-cols-12">
              {/* قائمة الكاميرات + الأرقام اللحظية */}
              <div className="flex flex-col gap-4 lg:col-span-3 lg:h-full lg:min-h-0">
                <Card className="flex max-h-[45vh] flex-1 flex-col overflow-hidden p-4 lg:max-h-none">
                  <div className="relative mb-4">
                    <Search className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      placeholder="بحث بالاسم أو الكود..."
                      aria-label="بحث عن كاميرا"
                      className="h-10 rounded-xl border-border/60 bg-muted/40 pe-9 text-sm focus:bg-card"
                      value={cameraSearch}
                      onChange={(e) => setCameraSearch(e.target.value)}
                    />
                  </div>

                  <div className="flex-1 space-y-2 overflow-y-auto pe-1">
                    {camerasError && cameraList.length === 0 ? (
                      <ErrorState compact title="تعذّر تحميل الكاميرات" onRetry={() => refetchCameras()} />
                    ) : camerasLoading && cameraList.length === 0 ? (
                      <div className="py-10 text-center text-sm text-muted-foreground">
                        <Loader2 className="mx-auto mb-2 size-4 animate-spin" />
                        جارٍ تحميل الكاميرات...
                      </div>
                    ) : cameraList.length === 0 ? (
                      <EmptyState
                        compact
                        icon={<CameraIcon className="size-6 text-primary" />}
                        title="لا توجد كاميرات بعد"
                        desc="اربط أول كاميرا وابدأ المراقبة الذكية خلال دقيقة."
                        action={
                          <button
                            type="button"
                            className="btn-cta text-sm"
                            onClick={() => {
                              setTab("cameras")
                              setAddOpen(true)
                            }}
                          >
                            <Plus className="size-4" /> أضف أول كاميرا
                          </button>
                        }
                      />
                    ) : filteredCams.length === 0 ? (
                      <div className="py-10 text-center text-sm text-muted-foreground">لا توجد نتائج للبحث</div>
                    ) : (
                      filteredCams.map((c) => {
                        const isSelected = selectedCamera?.id === c.id
                        const classes = c.enabled_classes ?? []
                        return (
                          <button
                            key={c.id}
                            type="button"
                            aria-pressed={isSelected}
                            onClick={() => selectCam(c.id)}
                            className={`group flex w-full items-start gap-3 rounded-xl border p-3.5 text-start transition-colors ${
                              isSelected ? "border-primary/30 bg-primary/12 shadow-md shadow-primary/5" : "border-transparent hover:bg-muted/40"
                            }`}
                          >
                            <span className="mt-1.5">
                              <LiveDot tone="success" active={c.is_running} />
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-2">
                                <span className="truncate text-sm font-bold text-foreground transition-colors group-hover:text-primary">{c.name}</span>
                                <span className={`shrink-0 text-[11px] font-bold ${c.is_running ? "text-success-foreground" : "text-muted-foreground"}`}>
                                  {c.is_running ? "تعمل" : "متوقفة"}
                                </span>
                              </div>
                              <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                                <span className="rounded border border-border/40 bg-card px-1.5 py-0.5 tabular-nums">#{c.id}</span>
                                <span className="truncate">{c.source_type}</span>
                              </div>
                              {classes.length > 0 && (
                                <div className="mt-2.5 flex flex-wrap gap-1">
                                  {classes.slice(0, 3).map((k) => (
                                    <span
                                      key={k}
                                      className="rounded-md border border-border/20 bg-secondary/50 px-1.5 py-0.5 text-[9px] font-medium text-secondary-foreground"
                                    >
                                      {ppeLabels.get(k) ?? k}
                                    </span>
                                  ))}
                                  {classes.length > 3 && <span className="self-end text-[9px] text-muted-foreground">+{classes.length - 3}</span>}
                                </div>
                              )}
                            </div>
                          </button>
                        )
                      })
                    )}
                  </div>
                </Card>

                {selectedCamera && (
                  <div className="grid grid-cols-2 gap-3">
                    <Card featured className="col-span-2 p-4 text-center">
                      <div className={`text-3xl font-bold tabular-nums ${compliance === undefined ? "text-muted-foreground" : "text-gradient"}`}>
                        {compliance === undefined ? "—" : `${compliance}%`}
                      </div>
                      <div className="mt-1 text-[11px] font-bold text-muted-foreground">نسبة الالتزام بالخوذة</div>
                      {!selectedCamera.is_running && <div className="mt-1 text-[11px] text-muted-foreground">شغّل الكاميرا لعرض البيانات</div>}
                      {selectedCamera.is_running && compliance === undefined && liveStatus === "open" && <div className="mt-1 text-[11px] text-muted-foreground">لا يوجد أشخاص في الكادر الآن</div>}
                    </Card>
                    <SideMetric icon={<Users className="size-4 text-info" />} value={selectedCamera.is_running ? counts.person_count : undefined} label="أشخاص" />
                    <SideMetric icon={<HardHat className="size-4 text-warning" />} value={selectedCamera.is_running ? counts.hardhat_count : undefined} label="خوذات" />
                    <SideMetric icon={<Shirt className="size-4 text-highlight" />} value={selectedCamera.is_running ? counts.vest_count : undefined} label="سترات" />
                    <SideMetric icon={<Boxes className="size-4 text-primary" />} value={selectedCamera.is_running ? counts.total_detections : undefined} label="إجمالي الكشف" />
                  </div>
                )}
              </div>

              {/* مسرح البث */}
              <div className="min-h-[360px] lg:col-span-9 lg:h-full lg:min-h-0">
                <Card className="relative aspect-video h-full overflow-hidden bg-black p-0 shadow-2xl shadow-black/30 lg:aspect-auto">
                  <LiveStage
                    camera={selectedCamera}
                    counts={counts}
                    status={liveStatus}
                    compliance={compliance}
                    pending={camPending}
                    onStart={() => selectedCamera && toggleCamera(selectedCamera)}
                    onStop={() => selectedCamera && toggleCamera(selectedCamera)}
                    onGoCameras={() => setTab("cameras")}
                  />
                </Card>
              </div>
            </div>
          )}

          {/* ===================== CAMERAS ===================== */}
          {tab === "cameras" && (
            <div className="mx-auto max-w-7xl space-y-6">
              <div className="card-premium flex flex-col justify-between gap-4 rounded-2xl border border-border/60 p-6 sm:flex-row sm:items-center">
                <div>
                  <h2 className="text-2xl font-bold text-foreground">إدارة مصادر الفيديو</h2>
                  <p className="mt-1.5 text-sm text-muted-foreground">اربط كاميرات RTSP وتحكم في تشغيلها وإيقافها من مكان واحد.</p>
                  {runningCount > MAX_GRID_PREVIEWS && <p className="mt-2 text-[11px] text-muted-foreground">تُعرض معاينة حية لأول {MAX_GRID_PREVIEWS} كاميرات فقط للحفاظ على الأداء.</p>}
                </div>

                <Dialog open={addOpen} onOpenChange={setAddOpen}>
                  <button type="button" className="btn-cta" onClick={() => setAddOpen(true)}>
                    <Plus className="size-4" /> إضافة كاميرا جديدة
                  </button>
                  <DialogContent className="max-w-lg rounded-2xl border-border bg-card">
                    <DialogHeader>
                      <DialogTitle className="font-bold text-foreground">ربط كاميرا جديدة بالنظام</DialogTitle>
                      <DialogDescription>أدخل رابط المصدر واختر معدات الوقاية المطلوب رصدها.</DialogDescription>
                    </DialogHeader>
                    <AddCameraForm
                      onSuccess={() => {
                        setAddOpen(false)
                        notify("success", "تمت إضافة الكاميرا بنجاح")
                      }}
                    />
                  </DialogContent>
                </Dialog>
              </div>

              {camerasError && cameraList.length === 0 ? (
                <ErrorState title="تعذّر تحميل الكاميرات" onRetry={() => refetchCameras()} />
              ) : camerasLoading && cameraList.length === 0 ? (
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                  {Array.from({ length: 4 }, (_, i) => (
                    <div key={i} className="card-premium overflow-hidden rounded-2xl border border-border/60">
                      <div className="skeleton-shimmer h-44" />
                      <div className="space-y-3 p-5">
                        <div className="skeleton-shimmer h-4 w-2/3 rounded" />
                        <div className="skeleton-shimmer h-3 w-full rounded" />
                        <div className="skeleton-shimmer h-8 w-full rounded-xl" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : cameraList.length === 0 ? (
                <EmptyState
                  icon={<CameraIcon className="size-6 text-primary" />}
                  title="ابدأ بربط أول كاميرا"
                  desc="أضف رابط RTSP أو مصدر فيديو، وسيبدأ النظام في رصد مخالفات معدات الوقاية تلقائيًا."
                  action={
                    <button type="button" className="btn-cta" onClick={() => setAddOpen(true)}>
                      <Plus className="size-4" /> أضف أول كاميرا خلال دقيقة
                    </button>
                  }
                />
              ) : (
                <div className="stagger grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                  {orderedCams.map((c) => (
                    <CameraCard
                      key={c.id}
                      camera={c}
                      ppeLabels={ppeLabels}
                      allowStream={previewAllowed.has(c.id)}
                      pending={togglingCamId === c.id}
                      deletePending={deletingCamId === c.id}
                      alerts={alertsByCam.get(c.id) ?? 0}
                      onToggle={() => toggleCamera(c)}
                      onWatch={() => selectCam(c.id)}
                      onEdit={() => openEdit(c)}
                      onDelete={() => askDelete(c)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ===================== VIOLATIONS ===================== */}
          {tab === "violations" && (
            <div className="mx-auto max-w-7xl space-y-6">
              <div className="card-premium flex flex-col justify-between gap-4 rounded-2xl border border-border/60 p-5 lg:flex-row lg:items-center">
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-destructive/15 p-2">
                    <ShieldAlert className="size-5 text-destructive" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold leading-tight text-foreground">سجل الحوادث والمخالفات</h2>
                    <p className="mt-0.5 text-xs text-muted-foreground">كل الانتهاكات المرصودة تلقائيًا في {rangeLabel}</p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="relative">
                    <select
                      aria-label="تصفية حسب الكاميرا"
                      className="h-10 min-w-[160px] cursor-pointer appearance-none rounded-xl border border-input bg-card py-2 pe-9 ps-3 text-sm shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-2 focus:ring-primary/25"
                      value={camFilter}
                      onChange={(e) => setCamFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
                    >
                      <option value="all">جميع الكاميرات ({totalCams})</option>
                      {cameraList.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  </div>

                  <div className="relative">
                    <select
                      aria-label="تصفية حسب نوع المخالفة"
                      className="h-10 min-w-[160px] cursor-pointer appearance-none rounded-xl border border-input bg-card py-2 pe-9 ps-3 text-sm shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-2 focus:ring-primary/25"
                      value={typeInput}
                      onChange={(e) => setTypeInput(e.target.value)}
                    >
                      <option value="">كل الأنواع</option>
                      {knownTypes.map((t) => (
                        <option key={t} value={t}>
                          {violationLabel(t, ppeLabels)}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  </div>

                  <SegToggle checked={showAllTypes} onChange={setShowAllTypes} labelOn="كل الأنواع" labelOff="معدات الوقاية" />

                  <Button asChild variant="outline" size="sm" className="gap-1.5 rounded-xl">
                    <a href={exportUrl} target="_blank" rel="noopener noreferrer">
                      <Download size={14} /> تصدير CSV
                    </a>
                  </Button>
                </div>
              </div>

              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full whitespace-nowrap text-start text-sm">
                    <thead className="border-b border-border bg-muted/60 text-xs font-semibold text-muted-foreground">
                      <tr>
                        <th className="p-4 text-start">الدليل المرئي</th>
                        <th className="p-4 text-start">التاريخ والوقت</th>
                        <th className="p-4 text-start">نوع المخالفة</th>
                        <th className="p-4 text-start">الكاميرا</th>
                        <th className="p-4 text-start">ثقة الكشف</th>
                        <th className="p-4 text-start">الحالة</th>
                        <th className="p-4 text-end">
                          <span className="sr-only">إجراءات</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/70">
                      {violationsError && !violationsRaw && (
                        <tr>
                          <td colSpan={7} className="p-6">
                            <ErrorState compact title="تعذّر تحميل المخالفات" onRetry={() => refetchViolations()} />
                          </td>
                        </tr>
                      )}

                      {loadingV && !violationsRaw && !violationsError && (
                        <>
                          {Array.from({ length: 5 }, (_, i) => (
                            <tr key={i}>
                              <td colSpan={7} className="p-4">
                                <div className="flex items-center gap-4">
                                  <div className="skeleton-shimmer h-10 w-14 rounded-xl" />
                                  <div className="flex-1 space-y-2">
                                    <div className="skeleton-shimmer h-4 w-48 rounded" />
                                    <div className="skeleton-shimmer h-3 w-24 rounded" />
                                  </div>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </>
                      )}

                      {!loadingV && !violationsError && filteredList.length === 0 && (
                        <tr>
                          <td colSpan={7} className="p-6">
                            <EmptyState
                              compact
                              icon={<ShieldCheck className="size-6 text-success" />}
                              title="لا توجد نتائج مطابقة"
                              desc="جرّب تغيير الفلاتر أو توسيع النطاق الزمني."
                            />
                          </td>
                        </tr>
                      )}

                      {pageItems.map((v) => {
                        const conf = Math.min(100, Math.max(0, Math.round(v.confidence * 100)))
                        const barColor = conf >= 85 ? "bg-success" : conf >= 60 ? "bg-warning" : "bg-destructive"
                        const resolvePending = resolvingViolationId === v.id

                        return (
                          <tr key={v.id} className="group transition-colors hover:bg-muted/60">
                            <td className="p-4">
                              <button
                                type="button"
                                onClick={() => openFrame(v.frame_url)}
                                disabled={!v.frame_url}
                                aria-label={v.frame_url ? "عرض اللقطة" : "لا توجد لقطة"}
                                className="block overflow-hidden rounded-xl border border-border/50 transition-all hover:border-primary/40 hover:shadow-md hover:shadow-primary/10 disabled:cursor-default disabled:hover:border-border/50 disabled:hover:shadow-none"
                              >
                                {v.frame_url ? (
                                  <img
                                    src={v.frame_url}
                                    loading="lazy"
                                    alt=""
                                    className="h-10 w-14 object-cover transition-transform duration-300 group-hover:scale-110"
                                  />
                                ) : (
                                  <div className="flex h-10 w-14 items-center justify-center bg-secondary text-muted-foreground">
                                    <ImageIcon size={16} />
                                  </div>
                                )}
                              </button>
                            </td>
                            <td className="p-4">
                              <div className="text-xs font-semibold text-foreground">{formatDate(v.timestamp)}</div>
                              <div className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">{formatTime(v.timestamp)}</div>
                            </td>
                            <td className="p-4">
                              <Badge variant={isCoreType(v.violation_type) ? "destructive" : "secondary"} className="rounded-md text-[11px] font-bold">
                                {violationLabel(v.violation_type, ppeLabels)}
                              </Badge>
                            </td>
                            <td className="p-4 text-xs text-muted-foreground">{cameraName(v.camera_id)}</td>
                            <td className="p-4">
                              <div className="flex items-center gap-2.5">
                                <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                                  <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${conf}%` }} />
                                </div>
                                <span className="w-9 text-xs font-bold tabular-nums text-foreground">{conf}%</span>
                              </div>
                            </td>

                            <td className="p-4">
                              {v.is_resolved ? (
                                <Badge variant="secondary" className="rounded-md text-[11px] font-bold">
                                  تمت المعالجة
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="rounded-md border-destructive/30 text-[11px] font-bold text-destructive">
                                  جديدة
                                </Badge>
                              )}
                            </td>

                            <td className="p-4 text-end">
                              <div className="flex justify-end gap-2">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  disabled={!v.frame_url}
                                  onClick={() => openFrame(v.frame_url)}
                                  className="h-8 gap-1.5 rounded-lg text-xs text-muted-foreground hover:bg-primary-light hover:text-primary"
                                >
                                  <Eye size={14} /> عرض
                                </Button>

                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  disabled={v.is_resolved || resolvePending}
                                  onClick={() => resolveViolation(v)}
                                  className="h-8 gap-1.5 rounded-lg text-xs text-muted-foreground hover:bg-success/10 hover:text-success-foreground disabled:opacity-50"
                                >
                                  {resolvePending ? <Loader2 className="size-3.5 animate-spin" /> : <ShieldCheck size={14} />}
                                  {v.is_resolved ? "مُعالجة" : "تعليم كمعالجة"}
                                </Button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/40 bg-muted/15 p-4 text-xs text-muted-foreground">
                  <span className="tabular-nums">
                    {filteredList.length === 0
                      ? "لا توجد سجلات"
                      : `عرض ${(safePage - 1) * TABLE_PAGE_SIZE + 1} إلى ${Math.min(safePage * TABLE_PAGE_SIZE, filteredList.length)} من ${filteredList.length}${
                          (violationsRaw?.items.length ?? 0) >= VIOLATIONS_FETCH_LIMIT ? "+" : ""
                        } سجل`}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button type="button" variant="outline" size="sm" className="h-7 rounded-lg text-[11px]" disabled={safePage <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                      السابق
                    </Button>
                    <span className="tabular-nums">
                      صفحة {safePage} من {pageCount}
                    </span>
                    <Button type="button" variant="outline" size="sm" className="h-7 rounded-lg text-[11px]" disabled={safePage >= pageCount} onClick={() => setPage((p) => Math.min(pageCount, p + 1))}>
                      التالي
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </div>
      </main>

      {/* ─── Edit Camera Modal ─── */}
      <Dialog
        open={editOpen}
        onOpenChange={(open) => {
          if (!open) {
            setEditOpen(false)
            setEditingCamera(null)
          }
        }}
      >
        <DialogContent className="max-w-lg rounded-2xl border-border bg-card">
          <DialogHeader>
            <DialogTitle className="font-bold text-foreground">تعديل الكاميرا</DialogTitle>
            <DialogDescription>يمكنك تعديل الاسم والرابط والفئات المفعّلة.</DialogDescription>
          </DialogHeader>
          {editingCamera && (
            <AddCameraForm
              key={editingCamera.id}
              mode="edit"
              camera={editingCamera}
              onSuccess={() => {
                setEditOpen(false)
                setEditingCamera(null)
                notify("success", "تم تحديث الكاميرا بنجاح")
              }}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* ─── Delete Confirm ─── */}
      <ConfirmDialog
        open={deleteOpen}
        title="تأكيد حذف الكاميرا"
        description={deleteTarget ? `هل أنت متأكد أنك تريد حذف «${deleteTarget.name}»؟` : undefined}
        confirmLabel="حذف"
        cancelLabel="إلغاء"
        tone="destructive"
        pending={deleteMut.isPending}
        onCancel={() => {
          if (deleteMut.isPending) return
          setDeleteOpen(false)
          setDeleteTarget(null)
        }}
        onConfirm={confirmDelete}
      />

      {/* ─── Frame Modal ─── */}
      <Dialog open={frameUrl !== null} onOpenChange={(open) => { if (!open) setFrameUrl(null) }}>
        <DialogContent className="max-w-5xl overflow-hidden rounded-2xl border-border bg-background p-0 shadow-2xl">
          <DialogHeader className="border-b border-border bg-card/90 p-4 text-start">
            <DialogTitle className="text-sm font-bold text-foreground">معاينة الدليل المرئي</DialogTitle>
            <DialogDescription className="text-xs">اللقطة التي رصد فيها النظام المخالفة</DialogDescription>
          </DialogHeader>
          <div className="flex min-h-[400px] items-center justify-center bg-black p-6">
            {frameUrl && (
              <img
                src={frameUrl}
                className="max-h-[75vh] max-w-full rounded-xl border border-white/10 shadow-[0_0_60px_rgba(0,0,0,0.6)]"
                alt="لقطة المخالفة"
              />
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  )
}

/* ─── مكوّن مساعد (function declaration مرفوعة تلقائيًا، فاستخدامها قبل التعريف سليم) ─── */

/** خانة رقم لحظي في اللوحة الجانبية بعدّاد متحرك، و"—" لما مفيش بث */
function SideMetric({ icon, value, label }: { icon: ReactNode; value: number | undefined; label: string }) {
  const animated = useCountUp(value)
  return (
    <div className="card-premium flex flex-col items-center justify-center gap-1 rounded-xl border border-border/50 p-3.5">
      {icon}
      <span className="text-lg font-bold tabular-nums">{animated ?? "—"}</span>
      <span className="text-[11px] font-bold text-muted-foreground">{label}</span>
    </div>
  )
}