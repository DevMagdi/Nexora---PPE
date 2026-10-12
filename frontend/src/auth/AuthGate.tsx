import { Suspense, lazy, useState } from "react"
import {
  Activity,
  AlertTriangle,
  Cctv,
  Eye,
  EyeOff,
  HardHat,
  Loader2,
  Lock,
  Moon,
  ShieldCheck,
  Stethoscope,
  Sun,
  User,
} from "lucide-react"
import PasswordChangeScreen from "@/auth/PasswordChangeScreen"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import nexoraLogoWhite from "@/assets/logo/nexora-logo-full-white.svg"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useLogin, useMe } from "@/hooks/useNexora"
import { useTheme } from "@/hooks/useUiHooks"
import { getErrorMessage } from "@/lib/utils"

const DashboardApp = lazy(() => import("@/App"))

const BRAND_FEATURES = [
  {
    icon: HardHat,
    title: "رصد مزدوج للإنشاءات والقطاع الطبي",
    desc: "نماذج ذكاء اصطناعي هجينة (Hybrid AI) مع فلاتر تحليل الجلد الدقيقة للقفازات والنظارات والكمامات والخوذات.",
  },
  {
    icon: Cctv,
    title: "مراقبة حية وتنبيهات لحظية",
    desc: "بث فيديو مباشر منخفض الكمون مع عدادات فورية وتوثيق مرئي تلقائي لكل مخالفة.",
  },
  {
    icon: ShieldCheck,
    title: "أمان مؤسسي محلي (On-Premise)",
    desc: "جلسات مشفرة بمعيار HttpOnly JWT، صلاحيات متعددة المستويات، وحماية كاملة لخصوصية الشبكة الداخلية.",
  },
]

export default function AuthGate() {
  const { data: me, isLoading } = useMe()
  const loginMut = useLogin()
  const [dark, setDark] = useTheme()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div
        className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background p-6"
        dir="rtl"
        lang="ar"
      >
        <div className="surface-floating flex flex-col items-center gap-4 px-8 py-7 text-center">
          <img
            src={dark ? nexoraLogoWhite : nexoraLogoColor}
            alt="Nexora"
            className="h-9 w-auto object-contain"
          />
          <div className="flex items-center gap-2.5 text-sm font-semibold text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-primary" />
            <span>جارٍ التحقق من الجلسة المشفّرة...</span>
          </div>
        </div>
      </div>
    )
  }

  if (me?.must_change_password) return <PasswordChangeScreen username={me.username} />
  if (me) {
    return (
      <Suspense
        fallback={
          <div
            className="flex min-h-dvh items-center justify-center gap-3 bg-background p-6 text-sm font-semibold text-muted-foreground"
            dir="rtl"
            lang="ar"
            role="status"
          >
            <Loader2 className="size-4 animate-spin text-primary" />
            جارٍ تحميل لوحة المراقبة...
          </div>
        }
      >
        <DashboardApp />
      </Suspense>
    )
  }

  async function onLogin(event: React.FormEvent) {
    event.preventDefault()
    setErr(null)
    try {
      await loginMut.mutateAsync({ username: username.trim(), password })
      setPassword("")
    } catch (error) {
      setErr(getErrorMessage(error, "فشل تسجيل الدخول"))
    }
  }

  return (
    <div
      className="relative flex min-h-dvh w-full flex-col bg-background lg:grid lg:grid-cols-12"
      dir="rtl"
      lang="ar"
    >
      {/* ─── Brand Showcase Panel (Desktop Split / VIP Identity) ─── */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-[#033024] via-[#064e3b] to-[#022c22] p-12 text-white lg:col-span-7 lg:flex lg:flex-col lg:justify-between xl:p-16">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(52, 211, 153, 0.45), transparent 45%), radial-gradient(circle at 80% 80%, rgba(14, 165, 233, 0.3), transparent 50%)",
          }}
        />

        <div className="relative z-10 flex items-center justify-between">
          <img
            src={nexoraLogoWhite}
            alt="Nexora"
            className="h-10 w-auto object-contain"
          />
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-950/60 px-3.5 py-1.5 text-xs font-semibold text-emerald-200 backdrop-blur-md">
            <Activity className="size-3.5 text-emerald-400" />
            <span>منظومة الرؤية الحاسوبية للسلامة المهنية</span>
          </div>
        </div>

        <div className="relative z-10 my-auto max-w-xl space-y-8 py-10">
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1 text-xs font-semibold text-emerald-100 ring-1 ring-white/15">
              <HardHat className="size-3.5 text-amber-300" /> قطاع الإنشاءات والمصانع
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1 text-xs font-semibold text-emerald-100 ring-1 ring-white/15">
              <Stethoscope className="size-3.5 text-sky-300" /> القطاع الطبي والمختبرات
            </span>
          </div>

          <div className="space-y-4">
            <h1 className="text-3xl font-bold leading-snug tracking-tight text-white xl:text-4xl">
              مراقبة ذكية للامتثال بمعدات الوقاية الشخصية في الوقت الفعلي
            </h1>
            <p className="text-base leading-relaxed text-emerald-100/80">
              تحليل فوري لتدفقات الكاميرات بدقة عالية، مع توثيق تلقائي للمخالفات ولوحة قيادة تنفيذية
              للمشرفين ومديري السلامة.
            </p>
          </div>

          <div className="space-y-4 pt-2">
            {BRAND_FEATURES.map((item) => {
              const Icon = item.icon
              return (
                <div
                  key={item.title}
                  className="flex items-start gap-4 rounded-2xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur-sm transition-colors hover:bg-white/[0.09]"
                >
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-400/30">
                    <Icon className="size-5" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-white">{item.title}</h2>
                    <p className="mt-1 text-xs leading-relaxed text-emerald-100/75">{item.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="relative z-10 flex items-center justify-between border-t border-white/10 pt-6 text-xs text-emerald-200/70">
          <span>Nexora PPE Platform · Enterprise Edition</span>
          <span className="font-mono text-[11px]" dir="ltr">
            On-Premise AI Vision
          </span>
        </div>
      </div>

      {/* ─── Login Form Panel ─── */}
      <div className="relative flex flex-1 flex-col justify-between p-6 sm:p-10 lg:col-span-5 lg:p-12">
        <div className="flex items-center justify-between">
          <div className="lg:hidden">
            <img
              src={dark ? nexoraLogoWhite : nexoraLogoColor}
              alt="Nexora"
              className="h-8 w-auto object-contain"
            />
          </div>
          <div className="hidden text-xs font-semibold text-muted-foreground lg:block">
            بوابة الدخول الموحّدة
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            aria-label={dark ? "التبديل إلى الوضع الفاتح" : "التبديل إلى الوضع الداكن"}
            onClick={() => setDark((d) => !d)}
            className="size-10 rounded-xl border border-border/60 bg-card hover:bg-muted"
          >
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </div>

        <div className="mx-auto my-auto w-full max-w-md py-8">
          <div className="card-premium border border-border/80 p-7 sm:p-9">
            <div className="mb-7">
              <div className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-primary-light px-3 py-1 text-xs font-bold text-primary">
                <ShieldCheck className="size-3.5" />
                <span>اتصال محلي آمن</span>
              </div>
              <h2 className="text-2xl font-bold text-foreground">تسجيل الدخول</h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                أدخل بيانات الحساب للوصول إلى لوحة مراقبة السلامة Nexora
              </p>
            </div>

            <form className="space-y-4" onSubmit={onLogin}>
              <div className="space-y-1.5">
                <Label htmlFor="login-username" className="text-xs font-bold text-foreground">
                  اسم المستخدم
                </Label>
                <div className="relative">
                  <User className="pointer-events-none absolute start-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="login-username"
                    name="username"
                    type="text"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="اسم المستخدم"
                    autoComplete="username"
                    required
                    maxLength={100}
                    className="h-11 rounded-xl ps-10"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="login-password" className="text-xs font-bold text-foreground">
                  كلمة المرور
                </Label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute start-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="login-password"
                    name="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="كلمة المرور"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    maxLength={128}
                    className="h-11 rounded-xl pe-11 ps-10"
                  />
                  <button
                    type="button"
                    aria-label={showPassword ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute end-1.5 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              {err && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 rounded-xl border border-destructive/30 bg-destructive-light p-3.5 text-xs font-semibold text-destructive-foreground animate-fade-in"
                >
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <span>{err}</span>
                </div>
              )}

              <Button
                className="btn-cta mt-2 h-11 w-full rounded-xl text-sm font-bold"
                type="submit"
                disabled={loginMut.isPending || isLoading}
              >
                {loginMut.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    جارٍ تسجيل الدخول...
                  </>
                ) : (
                  "دخول إلى لوحة العمليات"
                )}
              </Button>
            </form>
          </div>
        </div>

        <div className="text-center text-xs text-muted-foreground">
          محمي بواسطة سياسات القفل التلقائي والتشفير المحلي · Nexora PPE
        </div>
      </div>
    </div>
  )
}
