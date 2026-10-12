import { useMemo, useState } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Lock,
  ShieldCheck,
} from "lucide-react"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import nexoraLogoWhite from "@/assets/logo/nexora-logo-full-white.svg"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useChangePassword } from "@/hooks/useNexora"
import { useTheme } from "@/hooks/useUiHooks"
import { getErrorMessage } from "@/lib/utils"

interface PasswordChangeScreenProps {
  username: string
}

function countCharClasses(val: string): number {
  let c = 0
  if (/[a-z]/.test(val)) c++
  if (/[A-Z]/.test(val)) c++
  if (/\d/.test(val)) c++
  if (/[^A-Za-z0-9]/.test(val)) c++
  return c
}

export default function PasswordChangeScreen({ username }: PasswordChangeScreenProps) {
  const [dark] = useTheme()
  const mutation = useChangePassword()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const checks = useMemo(() => {
    const minLen = newPassword.length >= 12
    const classes = countCharClasses(newPassword) >= 3
    const noUsername =
      newPassword.length > 0 &&
      (!username || !newPassword.toLowerCase().includes(username.toLowerCase()))
    const matches = newPassword.length > 0 && newPassword === confirmPassword
    return [
      { id: "len", label: "12 حرفاً على الأقل", ok: minLen },
      { id: "classes", label: "3 أنواع على الأقل (أحرف كبيرة، صغيرة، أرقام، رموز)", ok: classes },
      { id: "user", label: "لا تحتوي على اسم المستخدم", ok: noUsername },
      { id: "match", label: "تطابق كلمة المرور الجديدة مع التأكيد", ok: matches },
    ]
  }, [newPassword, confirmPassword, username])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setErr(null)
    if (newPassword !== confirmPassword) {
      setErr("كلمتا المرور الجديدتان غير متطابقتين")
      return
    }
    try {
      await mutation.mutateAsync({ currentPassword, newPassword })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (error) {
      setErr(getErrorMessage(error, "تعذّر تغيير كلمة المرور"))
    }
  }

  return (
    <div
      className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-background p-4 sm:p-8"
      dir="rtl"
      lang="ar"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,var(--primary-light),transparent_55%),radial-gradient(ellipse_at_bottom_left,var(--info-light),transparent_55%)]"
      />

      <div className="surface-floating relative z-10 w-full max-w-lg animate-fade-in-up p-6 sm:p-9">
        <div className="mb-6 flex items-center justify-between">
          <img
            src={dark ? nexoraLogoWhite : nexoraLogoColor}
            alt="Nexora"
            className="h-9 w-auto object-contain"
          />
          <span className="inline-flex items-center gap-1.5 rounded-full bg-warning-light px-3 py-1 text-xs font-bold text-warning-foreground">
            <KeyRound className="size-3.5" /> إجراء أمني إلزامي
          </span>
        </div>

        <div className="mb-6">
          <h1 className="flex items-center gap-2 text-xl font-bold text-foreground sm:text-2xl">
            <ShieldCheck className="size-6 shrink-0 text-primary" />
            تعيين كلمة مرور دائمة
          </h1>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
            مرحباً <strong className="font-bold text-foreground">{username}</strong>، لحماية حسابك
            يرجى استبدال كلمة المرور المؤقتة بكلمة مرور قوية خاصة بك قبل المتابعة إلى لوحة العمليات.
          </p>
        </div>

        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-1.5">
            <Label htmlFor="current-password" className="text-xs font-bold text-foreground">
              كلمة المرور المؤقتة الحالية
            </Label>
            <div className="relative">
              <Lock className="pointer-events-none absolute start-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="current-password"
                type={showCurrent ? "text" : "password"}
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                placeholder="أدخل كلمة المرور المؤقتة"
                autoComplete="current-password"
                required
                maxLength={128}
                className="h-11 rounded-xl pe-11 ps-10"
              />
              <button
                type="button"
                aria-label={showCurrent ? "إخفاء كلمة المرور الحالية" : "إظهار كلمة المرور الحالية"}
                onClick={() => setShowCurrent((v) => !v)}
                className="absolute end-1.5 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {showCurrent ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="new-password" className="text-xs font-bold text-foreground">
              كلمة المرور الجديدة
            </Label>
            <div className="relative">
              <KeyRound className="pointer-events-none absolute start-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="new-password"
                type={showNew ? "text" : "password"}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="كلمة مرور قوية (12+ حرفاً)"
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
                className="h-11 rounded-xl pe-11 ps-10"
              />
              <button
                type="button"
                aria-label={showNew ? "إخفاء كلمة المرور الجديدة" : "إظهار كلمة المرور الجديدة"}
                onClick={() => setShowNew((v) => !v)}
                className="absolute end-1.5 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {showNew ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="confirm-password" className="text-xs font-bold text-foreground">
              تأكيد كلمة المرور الجديدة
            </Label>
            <div className="relative">
              <ShieldCheck className="pointer-events-none absolute start-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="confirm-password"
                type={showNew ? "text" : "password"}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="أعد كتابة كلمة المرور الجديدة"
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
                className="h-11 rounded-xl ps-10"
              />
            </div>
          </div>

          <div className="surface-flat space-y-2 p-3.5 text-xs">
            <div className="font-bold text-foreground">معايير الأمان المطلوبة:</div>
            <ul className="space-y-1.5">
              {checks.map((item) => (
                <li
                  key={item.id}
                  className={`flex items-center gap-2 transition-colors ${
                    item.ok ? "font-semibold text-success-foreground" : "text-muted-foreground"
                  }`}
                >
                  {item.ok ? (
                    <CheckCircle2 className="size-3.5 shrink-0 text-success" />
                  ) : (
                    <Circle className="size-3.5 shrink-0 opacity-45" />
                  )}
                  <span>{item.label}</span>
                </li>
              ))}
            </ul>
          </div>

          {err && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-xl border border-destructive/30 bg-destructive-light p-3.5 text-xs font-semibold text-destructive-foreground"
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
              <span>{err}</span>
            </div>
          )}

          <Button
            className="btn-cta h-11 w-full rounded-xl text-sm font-bold"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                جارٍ تحديث كلمة المرور وتأمين الجلسة...
              </>
            ) : (
              "حفظ كلمة المرور والمتابعة"
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}
