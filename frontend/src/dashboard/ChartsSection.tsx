import { ShieldCheck } from "lucide-react"
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { countFormatter, makeLabelFormatter, tooltipStyle, CHART_HEX, PIE_COLORS } from "@/lib/domain"
import type { ViolationChartPoint, ViolationTypePoint, RangeKey } from "@/types/app"
import { EmptyState } from "@/shared/EmptyState"
import { ErrorState } from "@/shared/ErrorState"
import { SegmentedToggle } from "@/shared/SegmentedToggle"
import { PremiumCard } from "@/shared/PremiumCard"

interface Props {
  range: RangeKey
  onRangeChange: (range: RangeKey) => void
  series: ViolationChartPoint[]
  pieData: ViolationTypePoint[]
  totalCount: number
  isCapped: boolean
  isLoading: boolean
  isError: boolean
  hasData: boolean
  rangeLabel: string
  onRetry: () => void
}

export function ChartsSection({ range, onRangeChange, series, pieData, totalCount, isCapped, isLoading, isError, hasData, rangeLabel, onRetry }: Props) {
  return (
    <section aria-label="تحليل المخالفات" className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <PremiumCard className="flex min-h-[380px] flex-col p-5 sm:p-6 lg:col-span-2">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-primary">الاتجاهات</p>
            <h3 className="mt-1 text-base font-bold">المخالفات عبر الوقت</h3>
            {isCapped && <p className="mt-1 text-[11px] text-muted-foreground">يعرض التحليل أحدث 200 سجل من إجمالي الفترة.</p>}
          </div>
          <SegmentedToggle checked={range === "7d"} onChange={(value) => onRangeChange(value ? "7d" : "24h")} labelOn="أسبوع" labelOff="يوم" ariaLabel="النطاق الزمني للرسم البياني" />
        </div>
        <div className="relative min-h-0 flex-1" dir="ltr">
          {isLoading && !hasData ? (
            <div className="skeleton-shimmer h-full min-h-64 rounded-xl" aria-label="جارٍ تحميل الرسم البياني" />
          ) : isError && !hasData ? (
            <div className="flex h-full items-center justify-center"><ErrorState compact title="تعذّر تحميل الرسم البياني" onRetry={onRetry} /></div>
          ) : !hasData ? (
            <div className="flex h-full items-center justify-center" dir="rtl">
              <EmptyState compact icon={<ShieldCheck className="size-5 text-success" />} title="لا توجد مخالفات في الفترة" desc={`لم يسجل النظام مخالفات خلال ${rangeLabel}.`} />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="violationsFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_HEX.green} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={CHART_HEX.green} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 4" stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} stroke="var(--chart-axis)" fontSize={11} interval="preserveStartEnd" minTickGap={28} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} stroke="var(--chart-axis)" fontSize={11} />
                <Tooltip contentStyle={tooltipStyle()} cursor={{ stroke: "var(--chart-axis)" }} formatter={countFormatter} labelFormatter={makeLabelFormatter(range === "24h" ? "الساعة" : "يوم")} />
                <Area type="monotone" dataKey="count" stroke={CHART_HEX.green} strokeWidth={2.5} fill="url(#violationsFill)" animationDuration={700} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </PremiumCard>

      <PremiumCard className="relative flex min-h-[380px] flex-col overflow-hidden p-5 sm:p-6">
        <div className="relative z-10 mb-2">
          <p className="text-xs font-semibold text-warning-foreground">التوزيع</p>
          <h3 className="mt-1 text-base font-bold">أنواع المخالفات</h3>
          {isCapped && <p className="mt-1 text-[11px] text-muted-foreground">التوزيع مبني على أحدث 200 سجل.</p>}
        </div>
        {isLoading && !hasData ? (
          <div className="skeleton-shimmer my-5 flex-1 rounded-2xl" aria-label="جارٍ تحميل التوزيع" />
        ) : isError && !hasData ? (
          <div className="flex flex-1 items-center justify-center"><ErrorState compact title="تعذّر تحميل التوزيع" onRetry={onRetry} /></div>
        ) : pieData.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <EmptyState compact icon={<ShieldCheck className="size-5 text-success" />} title="الموقع ملتزم" desc={`لم يُسجَّل أي انتهاك خلال ${rangeLabel}.`} />
          </div>
        ) : (
          <>
            <div className="relative min-h-0 flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={56} outerRadius={82} paddingAngle={4} dataKey="value" cornerRadius={8} animationDuration={700} stroke="none">
                    {pieData.map((item, index) => <Cell key={`${item.name}-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle()} formatter={countFormatter} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute start-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
                <div className="text-3xl font-bold tabular-nums">{totalCount}</div>
                <div className="mt-0.5 text-[11px] font-semibold text-muted-foreground">إجمالي الحالات</div>
              </div>
            </div>
            <div className="relative z-10 mt-3 space-y-2 border-t border-border/60 pt-3">
              {pieData.map((item, index) => (
                <div key={item.name} className="flex items-center justify-between gap-3 text-xs">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }} />
                    <span className="truncate font-medium text-muted-foreground">{item.name}</span>
                  </div>
                  <span className="rounded-md bg-muted/70 px-2 py-0.5 font-bold tabular-nums">{item.value}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </PremiumCard>
    </section>
  )
}
