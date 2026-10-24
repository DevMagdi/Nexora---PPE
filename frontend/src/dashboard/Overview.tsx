import { useState } from "react"
import {
  ArrowUpLeft,
  Cctv,
  Factory,
  FileClock,
  HardHat,
  PieChart as PieChartIcon,
  Radio,
  ShieldCheck,
  TriangleAlert,
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
import { Button } from "@/components/ui/button"
import { Empty, ErrorPanel, Loading } from "@/components/Feedback"
import EventTable from "@/violations/EventTable"
import { CHART_COLORS, LOCALE, classLabel, formatDate, formatTime, num } from "@/lib/formatters"
import { useViolations } from "@/hooks/useNexora"
import type { Camera, DashboardData, RangeKey, TabKey, Violation } from "@/types"

export default function Overview({
  data,
  loading,
  error,
  retry,
  range,
  siteId,
  cameras,
  canOperate,
  pendingId,
  onNavigate,
  onResolve,
  onEvidence,
}: {
  data?: DashboardData
  loading: boolean
  error: unknown
  retry: () => void
  range: RangeKey
  siteId?: number
  cameras: Camera[]
  canOperate: boolean
  pendingId?: number
  onNavigate: (tab: TabKey) => void
  onResolve: (id: number) => void
  onEvidence: (event: Violation) => void
}) {
  const [today] = useState(() => new Date().toISOString())
  const latest = useViolations({ page_size: 5, site_id: siteId, from: data?.from, to: data?.to })
  if (loading) return <Loading />
  if (error || !data) return <ErrorPanel error={error} retry={retry} />
  const cards = [
    {
      label: "الكاميرات قيد التشغيل",
      value: data.running_cameras,
      suffix: `/ ${num(data.total_cameras)}`,
      note: "مصادر ذات إطارات حديثة",
      icon: Cctv,
    },
    {
      label: "الأحداث المسجّلة",
      value: data.total_events,
      note: "مخالفات مثبتة خلال الفترة",
      icon: FileClock,
    },
    {
      label: "تنبيهات تحتاج متابعة",
      value: data.open_events,
      note: `${num(data.resolved_events)} حدث تمت معالجته`,
      icon: TriangleAlert,
      alert: true,
    },
    { label: "المصانع والمواقع", value: data.sites, note: "ضمن نطاق العرض المحدد", icon: Factory },
  ]
  return (
    <div className="space-y-6">
      <section className="industrial-hero">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-7">
          <div className="max-w-xl">
            <div className="eyebrow mb-3" dir="ltr">
              YOUR SITE. IN SIGHT.
            </div>
            <h2 className="industrial-hero-title text-2xl leading-relaxed">
              السلامة في قلب كل عملية.
            </h2>
            <p className="mt-3 text-xs leading-[2] text-muted-foreground">
              رؤية موحّدة لمعدات الوقاية في مصانعك ومواقعك. تابع المصادر المباشرة، وثّق المخالفات،
              وامنح فريق السلامة المعلومات اللازمة للاستجابة.
            </p>
            <div className="mt-5 flex flex-wrap gap-x-5 gap-y-3">
              <span className="hero-rule">
                <HardHat />
                معدات صناعية فقط
              </span>
              <span className="hero-rule">
                <ShieldCheck />
                استدلال محلي موحّد
              </span>
              <span className="hero-rule">
                <Radio />
                {num(data.live_people)} رصد أشخاص الآن
              </span>
            </div>
          </div>
          <div className="flex min-w-[150px] flex-col gap-4 border-s border-border ps-6">
            <p className="text-xs text-muted-foreground">{formatDate(today)}</p>
            <span className={`badge ${data.running_cameras ? "badge-success" : ""}`}>
              <span className="status-dot" />
              {data.running_cameras ? "المراقبة نشطة" : "المراقبة غير مفعّلة"}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate(canOperate && !cameras.length ? "cameras" : "live")}
            >
              {canOperate && !cameras.length ? "إضافة أول كاميرا" : "فتح البث المباشر"}
              <ArrowUpLeft />
            </Button>
          </div>
        </div>
      </section>
      <section
        className="grid grid-cols-2 gap-5 xl:grid-cols-4 sm:gap-7"
        aria-label="مؤشرات التشغيل"
      >
        {cards.map((item) => (
          <article className="panel metric-card" key={item.label}>
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-medium tracking-wide text-muted-foreground">
                {item.label}
              </p>
              <span
                className={`metric-icon ${item.alert && item.value ? "!border-destructive/25 !bg-destructive-light !text-destructive" : ""}`}
              >
                <item.icon />
              </span>
            </div>
            <div
              className={`metric-value ${item.alert && item.value ? "text-destructive" : "text-foreground"}`}
            >
              {num(item.value)}
              {item.suffix && (
                <span className="ms-2 text-sm text-muted-foreground">{item.suffix}</span>
              )}
            </div>
            <p className="mt-auto pt-4 text-[10px] leading-relaxed text-muted-foreground">
              {item.note}
            </p>
          </article>
        ))}
      </section>
      <div className="grid gap-7 xl:grid-cols-[1.7fr_1fr]">
        <section className="panel min-w-0">
          <div className="panel-header">
            <div>
              <h2>نشاط السلامة</h2>
              <p>{range === "24h" ? "آخر 24 ساعة، مجمّعة بالساعة" : "آخر 7 أيام، مجمّعة باليوم"}</p>
            </div>
            <span className="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span className="size-2 rounded-full" style={{ background: "var(--chart-gold)" }} />
              الأحداث
            </span>
          </div>
          <div
            className="h-[280px] px-3 pb-4 pt-6"
            dir="ltr"
            role="img"
            aria-label={`رسم نشاط السلامة: ${data.total_events} حدث`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.series} margin={{ top: 5, right: 15, bottom: 5, left: -25 }}>
                <defs>
                  <linearGradient id="mantik-activity-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--chart-gold)" stopOpacity={0.22} />
                    <stop offset="95%" stopColor="var(--chart-gold)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 6" vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(value) =>
                    range === "24h"
                      ? formatTime(value)
                      : new Date(value).toLocaleDateString(LOCALE, { weekday: "short" })
                  }
                  tick={{ fontSize: 10, fill: "var(--chart-axis)" }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={28}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "var(--chart-axis)" }}
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <div className="chart-tooltip" dir="rtl">
                        <p>
                          {range === "24h" ? formatTime(String(label)) : formatDate(String(label))}
                        </p>
                        <p className="mt-1 text-foreground">{num(Number(payload[0].value))} حدث</p>
                      </div>
                    ) : null
                  }
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="var(--chart-gold)"
                  strokeWidth={2}
                  fill="url(#mantik-activity-fill)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel min-w-0">
          <div className="panel-header">
            <div>
              <h2>توزيع المخالفات</h2>
              <p>حسب نوع معدات الوقاية</p>
            </div>
          </div>
          {data.total_events ? (
            <div className="px-6 pb-6">
              <div
                className="relative h-[180px]"
                dir="ltr"
                role="img"
                aria-label="التوزيع النسبي للمخالفات"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.breakdown}
                      dataKey="count"
                      nameKey="type"
                      innerRadius={58}
                      outerRadius={75}
                      stroke="var(--card)"
                      strokeWidth={4}
                      paddingAngle={3}
                      isAnimationActive={false}
                    >
                      {data.breakdown.map((item, index) => (
                        <Cell key={item.type} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="latin text-2xl">{num(data.total_events)}</span>
                  <span className="mt-1 text-[10px] text-muted-foreground">إجمالي الأحداث</span>
                </div>
              </div>
              <div className="space-y-2.5">
                {data.breakdown.map((item, index) => (
                  <div className="flex items-center justify-between text-[11px]" key={item.type}>
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <span
                        className="size-2 rounded-sm"
                        style={{ background: CHART_COLORS[index % CHART_COLORS.length] }}
                      />
                      {classLabel(item.type)}
                    </span>
                    <span className="latin">{num(item.count)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <Empty
              icon={<PieChartIcon />}
              title="لا توجد مخالفات مسجّلة"
              description="سيظهر توزيع الأحداث عند توفّر بيانات فعلية."
            />
          )}
        </section>
      </div>
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>آخر الأحداث</h2>
            <p>سجل الرصد الصناعي خلال الفترة المحددة</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => onNavigate("violations")}>
            عرض السجل
            <ArrowUpLeft />
          </Button>
        </div>
        {latest.isPending ? (
          <Loading />
        ) : latest.isError ? (
          <ErrorPanel error={latest.error} retry={() => void latest.refetch()} />
        ) : (
          <EventTable
            items={latest.data.items}
            cameras={cameras}
            canOperate={canOperate}
            pendingId={pendingId}
            onResolve={onResolve}
            onEvidence={onEvidence}
          />
        )}
      </section>
      <p className="text-[10px] leading-relaxed text-muted-foreground">
        الإحصائيات تمثّل أحداث الرصد، وليست عدداً فريداً للعاملين أو قياساً لنسبة الالتزام. مراجعة
        مشرف السلامة ضرورية قبل اتخاذ إجراء.
      </p>
    </div>
  )
}
