import type { ReactNode } from "react"
import { ArrowLeft, Image as ImageIcon, ShieldAlert, ShieldCheck } from "lucide-react"
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
  overviewError: boolean
  hasOverviewRaw: boolean
  onRetryOverview: () => void
  ppeLabels: Map<string, string>
  cameraName: (id: number) => string
  now: number
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
  overviewError,
  hasOverviewRaw,
  onRetryOverview,
  ppeLabels,
  cameraName,
  now,
  onOpenFrame,
  onGoViolations,
}: ChartsSectionProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <Card className="flex h-[420px] flex-col p-7 lg:col-span-2">
          <div className="mb-6 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="h-7 w-1.5 rounded-full bg-primary" />
              <h3 className="text-base font-semibold">المخالفات عبر الوقت</h3>
            </div>
            <SegToggle
              checked={range === "7d"}
              onChange={(v) => onRangeChange(v ? "7d" : "24h")}
              labelOn="أسبوعي"
              labelOff="يومي"
            />
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
                  animationDuration={1000}
                />
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
              {overviewError && !hasOverviewRaw ? (
                <ErrorState compact title="تعذّر تحميل بيانات المخالفات" onRetry={onRetryOverview} />
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
                      <span
                        className="size-2.5 rounded-md"
                        style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                      />
                      <span className="font-medium text-muted-foreground">{item.name}</span>
                    </div>
                    <span className="rounded-md bg-muted/60 px-2 py-0.5 font-bold tabular-nums">
                      {item.value}
                    </span>
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
            onClick={onGoViolations}
            className="flex items-center gap-1 text-[11px] font-bold text-primary underline-offset-2 hover:underline"
          >
            عرض السجل الكامل <ArrowLeft className="size-3" />
          </button>
        </div>

        <div className="max-h-[380px] divide-y divide-border/70 overflow-y-auto">
          {overviewError && !hasOverviewRaw ? (
            <div className="p-4">
              <ErrorState compact title="تعذّر تحميل التنبيهات" onRetry={onRetryOverview} />
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
              return (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => onOpenFrame(v.frame_url)}
                  disabled={!thumb}
                  className="group flex w-full items-center gap-4 p-4 text-start transition-colors hover:bg-muted/25 disabled:cursor-default disabled:hover:bg-transparent"
                >
                  {thumb ? (
                    <img
                      src={thumb}
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
                      <Badge
                        variant={isCoreType(v.violation_type) ? "destructive" : "secondary"}
                        className="rounded-md px-2 py-0.5 text-[11px] font-bold"
                      >
                        {violationLabel(v.violation_type, ppeLabels)}
                      </Badge>
                      <span className="text-[11px] text-muted-foreground">
                        {formatRelative(v.timestamp, now)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="truncate font-medium text-foreground/85">
                        {cameraName(v.camera_id)}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        ثقة الكشف{" "}
                        <strong className="tabular-nums text-foreground">
                          {Math.round(v.confidence * 100)}%
                        </strong>
                      </span>
                    </div>
                  </div>
                  {thumb && (
                    <ArrowLeft className="size-4 text-muted-foreground/25 transition-all duration-300 group-hover:-translate-x-1 group-hover:text-primary" />
                  )}
                </button>
              )
            })
          )}
        </div>
      </Card>
    </>
  )
}
