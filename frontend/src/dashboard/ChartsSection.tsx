import type { ReactNode } from "react"
import {
  ArrowLeft,
  Eye,
  Image as ImageIcon,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { resolveFrameUrl } from "@/lib/api"
import {
  CHART_HEX,
  formatRelative,
  isCoreType,
  PIE_COLORS,
  violationLabel,
} from "@/lib/formatters"
import Card from "@/shared/Card"
import EmptyState from "@/shared/EmptyState"
import ErrorState from "@/shared/ErrorState"
import SegToggle from "@/shared/SegToggle"
import SkeletonBlock from "@/shared/SkeletonBlock"
import type { RangeKey, Violation } from "@/types"

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

function countFormatter(value: unknown, name?: unknown): [string, string] {
  const num = Array.isArray(value) ? value.length : Number(value ?? 0)
  return [`${Number.isFinite(num) ? num : 0} مخالفة`, name ? String(name) : ""]
}

function makeLabelFormatter(prefix: string) {
  return (label: ReactNode) => `${prefix} ${label == null ? "" : String(label)}`
}

interface ChartsSectionProps {
  range: RangeKey
  onRangeChange: (next: RangeKey) => void
  rangeLabel: string
  series: { label: string; count: number }[]
  pieData: { name: string; value: number }[]
  overviewList: Violation[]
  overviewCapped: boolean
  overviewLoading?: boolean
  overviewError: boolean
  hasOverviewRaw: boolean
  onRetryOverview: () => void
  ppeLabels: Map<string, string>
  cameraName: (id: number) => string
  now: number
  canOperate?: boolean
  resolvingViolationId?: number | null
  onResolveViolation?: (v: Violation) => void
  onOpenFrame: (url?: string | null) => void
  onGoViolations: () => void
}

export default function ChartsSection({
  range,
  onRangeChange,
  rangeLabel,
  series,
  pieData,
  overviewList,
  overviewCapped,
  overviewLoading = false,
  overviewError,
  hasOverviewRaw,
  onRetryOverview,
  ppeLabels,
  cameraName,
  now,
  canOperate = false,
  resolvingViolationId = null,
  onResolveViolation,
  onOpenFrame,
  onGoViolations,
}: ChartsSectionProps) {
  const totalInSeries = series.reduce((sum, item) => sum + item.count, 0)

  return (
    <>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:gap-8">
        {/* ─── Area Chart: Violations Over Time ─── */}
        <Card className="flex h-[420px] flex-col p-6 sm:p-7 lg:col-span-2">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex size-9 items-center justify-center rounded-xl bg-primary-light text-primary">
                <TrendingUp className="size-4.5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-foreground">المخالفات عبر الوقت</h3>
                <p className="text-xs text-muted-foreground">
                  التوزيع الزمني للتنبيهات خلال {rangeLabel}
                </p>
              </div>
            </div>
            <SegToggle
              checked={range === "7d"}
              onChange={(v) => onRangeChange(v ? "7d" : "24h")}
              labelOn="أسبوعي"
              labelOff="يومي"
            />
          </div>

          {overviewError && !hasOverviewRaw ? (
            <div className="flex flex-1 items-center justify-center">
              <ErrorState compact title="تعذّر تحميل السلسلة الزمنية" onRetry={onRetryOverview} />
            </div>
          ) : overviewLoading && !hasOverviewRaw ? (
            <div className="flex flex-1 flex-col justify-end gap-3 pt-4">
              <SkeletonBlock className="h-56 w-full rounded-2xl" />
              <div className="flex justify-between gap-2">
                <SkeletonBlock className="h-3 w-12 rounded" />
                <SkeletonBlock className="h-3 w-12 rounded" />
                <SkeletonBlock className="h-3 w-12 rounded" />
                <SkeletonBlock className="h-3 w-12 rounded" />
              </div>
            </div>
          ) : totalInSeries === 0 ? (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState
                compact
                icon={<ShieldCheck className="size-6 text-success" />}
                title="سجل زمني نظيف"
                desc={`لم تُسجَّل أي مخالفات على مدار ${rangeLabel}.`}
              />
            </div>
          ) : (
            <div className="min-h-0 w-full flex-1" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={series} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <defs>
                    <linearGradient id="violationsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_HEX.green} stopOpacity={0.32} />
                      <stop offset="95%" stopColor={CHART_HEX.green} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 4"
                    stroke="var(--chart-grid)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    stroke="var(--chart-axis)"
                    fontSize={11}
                    interval="preserveStartEnd"
                    minTickGap={28}
                  />
                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    stroke="var(--chart-axis)"
                    fontSize={11}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle()}
                    cursor={{ stroke: "var(--chart-axis)" }}
                    formatter={countFormatter}
                    labelFormatter={makeLabelFormatter(range === "24h" ? "الساعة" : "يوم")}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke={CHART_HEX.green}
                    strokeWidth={2.5}
                    fill="url(#violationsFill)"
                    animationDuration={900}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        {/* ─── Donut Chart: Violation Types Breakdown ─── */}
        <Card className="relative flex h-[420px] flex-col overflow-hidden p-6 sm:p-7">
          <div className="relative z-10 mb-4 flex items-center gap-3">
            <div className="h-7 w-1.5 rounded-full bg-warning" />
            <div>
              <h3 className="text-base font-bold text-foreground">توزيع أنواع المخالفات</h3>
              <p className="text-xs text-muted-foreground">أعلى الفئات تكراراً</p>
            </div>
          </div>

          {overviewError && !hasOverviewRaw ? (
            <div className="relative z-10 flex flex-1 items-center justify-center">
              <ErrorState compact title="تعذّر تحميل بيانات المخالفات" onRetry={onRetryOverview} />
            </div>
          ) : overviewLoading && !hasOverviewRaw ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4">
              <SkeletonBlock className="size-40 rounded-full" />
              <div className="w-full space-y-2">
                <SkeletonBlock className="h-4 w-full rounded" />
                <SkeletonBlock className="h-4 w-4/5 rounded" />
              </div>
            </div>
          ) : pieData.length === 0 ? (
            <div className="relative z-10 flex flex-1 items-center justify-center">
              <EmptyState
                compact
                icon={<ShieldCheck className="size-6 text-success" />}
                title="الموقع ملتزم"
                desc={`لم يُسجَّل أي انتهاك في ${rangeLabel}. استمر على هذا المستوى.`}
              />
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
                      innerRadius={56}
                      outerRadius={80}
                      paddingAngle={4}
                      dataKey="value"
                      cornerRadius={8}
                      animationDuration={800}
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
                  <div className="mt-0.5 text-[11px] font-bold text-muted-foreground">
                    إجمالي الحالات
                  </div>
                </div>
              </div>
              <div className="relative z-10 mt-3 space-y-2 border-t border-border/50 pt-4">
                {pieData.map((item, i) => (
                  <div key={item.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span
                        className="size-2.5 shrink-0 rounded-md"
                        style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                      />
                      <span className="truncate font-medium text-muted-foreground">
                        {item.name}
                      </span>
                    </div>
                    <span className="rounded-md bg-muted/70 px-2 py-0.5 font-bold tabular-nums text-foreground">
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* ─── Recent Alerts Feed ─── */}
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-border/50 bg-card/80 p-5">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-xl bg-destructive-light text-destructive">
              <ShieldAlert className="size-4.5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-foreground">آخر التنبيهات المسجلة</h3>
              <p className="text-xs text-muted-foreground">أحدث الحوادث الموثقة بالصور</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onGoViolations}
            className="flex min-h-9 items-center gap-1.5 rounded-xl bg-primary-light px-3.5 py-1.5 text-xs font-bold text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
          >
            <span>عرض السجل الكامل</span>
            <ArrowLeft className="size-3.5" />
          </button>
        </div>

        <div className="max-h-[420px] divide-y divide-border/60 overflow-y-auto">
          {overviewError && !hasOverviewRaw ? (
            <div className="p-4">
              <ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={onRetryOverview} />
            </div>
          ) : overviewLoading && !hasOverviewRaw ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 3 }, (_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <SkeletonBlock className="size-14 rounded-xl" />
                  <div className="flex-1 space-y-2">
                    <SkeletonBlock className="h-4 w-40 rounded" />
                    <SkeletonBlock className="h-3 w-28 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : overviewList.length === 0 ? (
            <EmptyState
              compact
              icon={<ShieldCheck className="size-6 text-success" />}
              title="كل شيء على ما يرام"
              desc={`لم يرصد النظام أي مخالفات في ${rangeLabel}.`}
            />
          ) : (
            overviewList.slice(0, 6).map((v) => {
              const thumb = resolveFrameUrl(v.frame_url)
              const resolvePending = resolvingViolationId === v.id
              return (
                <div
                  key={v.id}
                  className="group flex flex-wrap items-center justify-between gap-4 p-4 transition-colors hover:bg-muted/35"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-4">
                    <button
                      type="button"
                      onClick={() => onOpenFrame(v.frame_url)}
                      disabled={!thumb}
                      aria-label={thumb ? "عرض لقطة المخالفة" : "لا توجد لقطة"}
                      className="relative shrink-0 overflow-hidden rounded-xl border border-border/60 disabled:cursor-default"
                    >
                      {thumb ? (
                        <img
                          src={thumb}
                          loading="lazy"
                          alt={`لقطة ${violationLabel(v.violation_type, ppeLabels)}`}
                          className="size-14 object-cover transition-transform duration-300 group-hover:scale-105"
                        />
                      ) : (
                        <div className="flex size-14 items-center justify-center bg-secondary text-muted-foreground">
                          <ImageIcon className="size-5 opacity-50" />
                        </div>
                      )}
                    </button>

                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant={isCoreType(v.violation_type) ? "destructive" : "secondary"}
                          className="rounded-md px-2 py-0.5 text-[11px] font-bold"
                        >
                          {violationLabel(v.violation_type, ppeLabels)}
                        </Badge>
                        {v.is_resolved ? (
                          <span className="rounded-md bg-success-light px-2 py-0.5 text-[10px] font-bold text-success-foreground">
                            تمت المعالجة
                          </span>
                        ) : (
                          <span className="rounded-md bg-destructive-light px-2 py-0.5 text-[10px] font-bold text-destructive-foreground">
                            جديدة
                          </span>
                        )}
                        <span className="text-[11px] text-muted-foreground">
                          {formatRelative(v.timestamp, now)}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="truncate font-semibold text-foreground/90">
                          {cameraName(v.camera_id)}
                        </span>
                        <span className="text-muted-foreground">·</span>
                        <span className="text-[11px] text-muted-foreground">
                          ثقة الكشف{" "}
                          <strong className="tabular-nums text-foreground">
                            {Math.round(v.confidence * 100)}%
                          </strong>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {thumb && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onOpenFrame(v.frame_url)}
                        className="h-9 gap-1.5 rounded-xl text-xs text-muted-foreground hover:bg-primary-light hover:text-primary"
                      >
                        <Eye className="size-3.5" />
                        <span>اللقطة</span>
                      </Button>
                    )}
                    {canOperate && onResolveViolation && !v.is_resolved && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={resolvePending}
                        onClick={() => onResolveViolation(v)}
                        className="h-9 gap-1.5 rounded-xl text-xs font-semibold hover:border-success/40 hover:bg-success-light hover:text-success-foreground"
                      >
                        {resolvePending ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <ShieldCheck className="size-3.5 text-success" />
                        )}
                        <span>معالجة</span>
                      </Button>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </Card>
    </>
  )
}
