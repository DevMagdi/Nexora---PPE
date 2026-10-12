import { useState } from "react"
import { Loader2 } from "lucide-react"
import App from "@/App"
import PasswordChangeScreen from "@/auth/PasswordChangeScreen"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useLogin, useMe } from "@/hooks/useNexora"
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

          {err && (
            <div role="alert" className="text-sm text-destructive">
              {err}
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
