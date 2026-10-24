import { Suspense, lazy, useState } from "react"
import { isAxiosError } from "axios"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Cctv,
  Eye,
  EyeOff,
  Factory,
  HardHat,
  Loader2,
  LockKeyhole,
  ShieldCheck,
  UserRound,
} from "lucide-react"
import Brand from "@/components/Brand"
import { InlineError, Loading } from "@/components/Feedback"
import { Button } from "@/components/ui/button"
import PasswordChangeScreen from "@/auth/PasswordChangeScreen"
import { useMe } from "@/hooks/useNexora"
import { login } from "@/lib/api"

const DashboardApp = lazy(() => import("@/App"))

export default function AuthGate() {
  const [year] = useState(() => new Date().getFullYear())
  const session = useMe()
  const serverUnavailable =
    session.isError &&
    (!isAxiosError(session.error) ||
      !session.error.response ||
      session.error.response.status >= 500)
  const client = useQueryClient()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [visible, setVisible] = useState(false)
  const mutation = useMutation({
    mutationFn: () => login(username.trim(), password),
    onSuccess: async () => {
      setPassword("")
      await client.invalidateQueries({ queryKey: ["me"] })
    },
  })

  if (session.isPending)
    return (
      <main className="grid min-h-dvh place-items-center">
        <div>
          <Brand />
          <Loading label="جارٍ التحقق من الجلسة…" />
        </div>
      </main>
    )
  if (session.data?.must_change_password)
    return <PasswordChangeScreen username={session.data.username} />
  if (session.data)
    return (
      <Suspense fallback={<Loading />}>
        <DashboardApp user={session.data} />
      </Suspense>
    )

  return (
    <main className="login-screen" dir="rtl" lang="ar">
      <section className="login-story">
        <div className="flex items-center justify-between gap-4">
          <Brand />
          <span className="badge latin text-[9px]">PPE / V4.0</span>
        </div>
        <div className="login-story-main">
          <div className="eyebrow mb-5" dir="ltr">
            PRECISION. PROTECTION. CONFIDENCE.
          </div>
          <h1>
            رؤية أوضح.
            <br />
            <span className="text-foreground">مواقع أكثر أماناً.</span>
          </h1>
          <p className="mt-5 max-w-md text-sm leading-[2] text-muted-foreground">
            منصة مراقبة السلامة الصناعية. حوّل كاميرات موقعك إلى رؤية تشغيلية تساعد فريقك على رصد
            مخالفات معدات الوقاية والاستجابة لها.
          </p>
          <div className="mt-10 border-t border-border pt-5">
            <div className="login-feature">
              <HardHat />
              <div>
                <h2>سلامة المصانع ومواقع الإنشاء</h2>
                <p>رصد الخوذ والسترات والقفازات وأحذية الأمان والنظارات الواقية.</p>
              </div>
            </div>
            <div className="login-feature">
              <Cctv />
              <div>
                <h2>من الصورة إلى الحدث الموثّق</h2>
                <p>كاميرات RTSP، رفع الصور والفيديو، وتنبيهات مع أدلة مرئية.</p>
              </div>
            </div>
            <div className="login-feature">
              <ShieldCheck />
              <div>
                <h2>تحكّم محلي بصلاحيات واضحة</h2>
                <p>مدير نظام، مشرف سلامة، ومشاهد. بيانات موقعك داخل بيئتك.</p>
              </div>
            </div>
          </div>
        </div>
        <div className="login-story-footer flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-2">
            <Factory className="size-4 text-primary" />
            مصانع · مواقع إنشاء · ورش · مستودعات
          </span>
          <span className="eyebrow !text-[8px]">INDUSTRIAL ONLY</span>
        </div>
      </section>
      <section className="login-form-panel">
        <div className="hidden items-center justify-between text-[11px] text-muted-foreground md:flex">
          <span>بوابة العمليات</span>
          <span className="flex items-center gap-2">
            <LockKeyhole className="size-3.5 text-primary" />
            وصول مصرّح به فقط
          </span>
        </div>
        <div className="login-card">
          <div className="mb-7">
            <div className="mb-5 grid size-12 place-items-center rounded-xl border border-border bg-accent text-primary">
              <ShieldCheck className="size-6" strokeWidth={1.4} />
            </div>
            <div className="eyebrow mb-2" dir="ltr">
              WELCOME TO NEXORA
            </div>
            <h2 className="text-[28px]">تسجيل الدخول</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              أدخل بياناتك للوصول إلى غرفة عمليات السلامة.
            </p>
          </div>
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault()
              mutation.mutate()
            }}
          >
            <div>
              <label className="field-label" htmlFor="login-username">
                اسم المستخدم
              </label>
              <div className="login-input-wrap">
                <UserRound />
                <input
                  id="login-username"
                  name="username"
                  className="field"
                  autoComplete="username"
                  placeholder="أدخل اسم المستخدم"
                  required
                  maxLength={100}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="field-label" htmlFor="login-password">
                كلمة المرور
              </label>
              <div className="login-input-wrap">
                <LockKeyhole />
                <input
                  id="login-password"
                  name="password"
                  className="field !pe-11"
                  autoComplete="current-password"
                  type={visible ? "text" : "password"}
                  placeholder="أدخل كلمة المرور"
                  required
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="absolute end-2 top-1 grid size-9 place-items-center rounded text-muted-foreground hover:text-primary"
                  onClick={() => setVisible(!visible)}
                  aria-label={visible ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
                >
                  {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>
            {serverUnavailable && (
              <div className="notice" role="alert">
                <p>
                  الخادم غير متاح حالياً. تحقّق من تشغيل الخدمة ونجاح فحص الموديل المعتمد قبل تسجيل
                  الدخول.
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-2"
                  onClick={() => void session.refetch()}
                  disabled={session.isFetching}
                >
                  إعادة التحقق من الخادم
                </Button>
              </div>
            )}
            <InlineError error={mutation.error} />
            <Button
              type="submit"
              className="h-11 w-full font-semibold"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? <Loader2 className="animate-spin" /> : <LockKeyhole />}
              {mutation.isPending ? "جارٍ تسجيل الدخول…" : "الدخول إلى لوحة العمليات"}
            </Button>
          </form>
          <div className="mt-7 border-t border-border pt-5 text-[11px] leading-[1.9] text-muted-foreground">
            بيانات الدخول يوفّرها مسؤول الموقع. يُطلب تغيير كلمة المرور المؤقتة عند أول دخول.
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 text-[10px] text-muted-foreground">
          <span className="latin tracking-wide">NEXORA © {year}</span>
          <span>السلامة معيار التشغيل.</span>
        </div>
      </section>
    </main>
  )
}
