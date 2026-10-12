import { useState } from "react"
import { Loader2, ShieldCheck } from "lucide-react"
import App from "@/App"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useChangePassword, useLogin, useMe } from "@/hooks/useNexora"
import { getErrorMessage } from "@/lib/utils"

export default function AuthGate() {
  const { data: me, isLoading } = useMe()
  const loginMut = useLogin()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [err, setErr] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-background p-6" dir="rtl">
        <div className="flex items-center gap-2.5 text-sm font-medium text-muted-foreground">
          <Loader2 className="size-4 animate-spin text-primary" />
          <span>جارٍ التحقق من الجلسة...</span>
        </div>
      </div>
    )
  }

  if (me?.must_change_password) return <PasswordChangeScreen username={me.username} />
  if (me) return <App />

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
    <div className="flex min-h-dvh items-center justify-center bg-background p-6" dir="rtl">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-7 shadow-xl">
        <div className="mb-5 flex justify-center">
          <img src={nexoraLogoColor} alt="Nexora" className="h-9 w-auto object-contain" />
        </div>
        <div className="text-center text-xl font-bold">تسجيل الدخول</div>
        <div className="mt-1 text-center text-sm text-muted-foreground">
          أدخل بيانات الحساب للوصول إلى لوحة مراقبة السلامة Nexora
        </div>

        <form className="mt-6 space-y-3.5" onSubmit={onLogin}>
          <Input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="اسم المستخدم"
            autoComplete="username"
            required
            maxLength={100}
          />
          <Input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="كلمة المرور"
            type="password"
            autoComplete="current-password"
            required
            maxLength={128}
          />

          <Button className="w-full" type="submit" disabled={loginMut.isPending || isLoading}>
            {loginMut.isPending ? "جارٍ تسجيل الدخول..." : "دخول"}
          </Button>

          {err && <div role="alert" className="text-sm text-destructive">{err}</div>}
        </form>
      </div>
    </div>
  )
}

function PasswordChangeScreen({ username }: { username: string }) {
  const mutation = useChangePassword()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [err, setErr] = useState<string | null>(null)

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
    <div className="flex min-h-dvh items-center justify-center bg-background p-6" dir="rtl">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-7 shadow-xl">
        <div className="mb-5 flex justify-center">
          <img src={nexoraLogoColor} alt="Nexora" className="h-9 w-auto object-contain" />
        </div>
        <div className="mb-2 flex items-center justify-center gap-2 text-center text-xl font-bold">
          <ShieldCheck className="size-5 text-primary" /> تغيير كلمة المرور المؤقتة
        </div>
        <p className="text-center text-sm text-muted-foreground">
          أهلاً {username}، يجب تعيين كلمة مرور جديدة قبل استخدام النظام.
        </p>
        <form className="mt-6 space-y-3.5" onSubmit={submit}>
          <Input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            placeholder="كلمة المرور المؤقتة الحالية"
            autoComplete="current-password"
            required
            maxLength={128}
          />
          <Input
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder="كلمة المرور الجديدة"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={128}
          />
          <Input
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="تأكيد كلمة المرور الجديدة"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={128}
          />
          <p className="text-xs leading-5 text-muted-foreground">
            استخدم 12 حرفاً على الأقل وثلاثة أنواع من الأحرف على الأقل؛ لا تستخدم اسم المستخدم.
          </p>
          <Button className="w-full" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "جارٍ تحديث كلمة المرور..." : "حفظ والمتابعة"}
          </Button>
          {err && <div role="alert" className="text-sm text-destructive">{err}</div>}
        </form>
      </div>
    </div>
  )
}
