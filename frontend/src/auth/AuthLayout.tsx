import type { ReactNode } from "react"
import { ShieldCheck, Sparkles } from "lucide-react"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import nexoraLogoWhite from "@/assets/logo/nexora-logo-full-white.svg"

export function AuthLayout({ children, title, description, mode = "light" }: { children: ReactNode; title: string; description: string; mode?: "light" | "dark" }) {
  return (
    <main className="auth-canvas flex min-h-dvh items-center justify-center p-3 sm:p-6" dir="rtl" lang="ar">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-border/80 bg-card shadow-floating lg:min-h-[620px] lg:grid-cols-2">
        <section className="relative hidden overflow-hidden bg-gradient-to-br from-emerald-950 via-emerald-900 to-teal-800 p-10 text-white lg:flex lg:flex-col lg:justify-between xl:p-14">
          <div aria-hidden="true" className="auth-orb auth-orb-one" />
          <div aria-hidden="true" className="auth-orb auth-orb-two" />
          <div className="relative z-10">
            <img src={nexoraLogoWhite} alt="Nexora" className="h-10 w-auto object-contain" />
            <p className="mt-2 text-xs font-medium tracking-wide text-white/55">منصة مراقبة السلامة الذكية</p>
          </div>
          <div className="relative z-10 max-w-md">
            <div className="mb-5 flex size-12 items-center justify-center rounded-2xl border border-white/10 bg-white/10 text-emerald-100"><ShieldCheck className="size-6" /></div>
            <p className="mb-3 text-xs font-bold tracking-[0.18em] text-emerald-200">NEXORA OPERATIONS</p>
            <h1 className="text-3xl font-bold leading-[1.35] tracking-tight xl:text-4xl">سلامة أوضح.<br />قرارات أسرع.</h1>
            <p className="mt-4 max-w-sm text-sm leading-7 text-white/70">مراقبة لحظية لمعدات الوقاية، تنبيهات موثوقة، ورؤية موحّدة لكل مواقع العمل.</p>
            <div className="mt-8 flex flex-wrap gap-2 text-xs font-semibold text-white/80">
              <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5">تحليل مباشر</span>
              <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5">إنشاءات وقطاع طبي</span>
              <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5">خصوصية محلية</span>
            </div>
          </div>
          <div className="relative z-10 flex items-center gap-2 text-xs text-white/50"><Sparkles className="size-3.5" /> Nexora · PPE Intelligence</div>
        </section>

        <section className="flex min-w-0 flex-col justify-center p-6 sm:p-9 lg:p-10 xl:p-14">
          <div className="mb-8 lg:hidden">
            <img src={mode === "dark" ? nexoraLogoWhite : nexoraLogoColor} alt="Nexora" className="h-8 w-auto object-contain" />
            <p className="mt-2 text-xs font-medium text-muted-foreground">منصة مراقبة السلامة الذكية</p>
          </div>
          <div className="mb-7">
            <p className="mb-2 text-xs font-bold tracking-wide text-primary">NEXORA PPE</p>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
          </div>
          {children}
          <p className="mt-8 text-center text-[11px] leading-5 text-muted-foreground/75">وصول آمن · تُدار الصلاحيات من قبل مسؤول النظام</p>
        </section>
      </div>
    </main>
  )
}

export function AuthLoadingScreen() {
  return (
    <main className="auth-canvas flex min-h-dvh items-center justify-center p-6" dir="rtl" lang="ar">
      <div className="w-full max-w-5xl overflow-hidden rounded-[28px] border border-border bg-card shadow-floating sm:grid sm:min-h-[560px] sm:grid-cols-2">
        <div className="hidden bg-gradient-to-br from-emerald-950 to-teal-800 p-10 sm:block" />
        <div className="flex flex-col justify-center p-8 sm:p-12" role="status" aria-live="polite">
          <img src={nexoraLogoColor} alt="Nexora" className="mb-8 h-9 w-auto self-start object-contain" />
          <div className="skeleton-shimmer h-6 w-36 rounded-lg" />
          <div className="mt-3 skeleton-shimmer h-4 w-56 rounded" />
          <div className="mt-8 skeleton-shimmer h-11 w-full rounded-xl" />
          <div className="mt-3 skeleton-shimmer h-11 w-full rounded-xl" />
          <p className="mt-6 text-xs text-muted-foreground">جارٍ التحقق من الجلسة الآمنة...</p>
        </div>
      </div>
    </main>
  )
}
