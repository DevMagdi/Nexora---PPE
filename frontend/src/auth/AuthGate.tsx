import { useState } from "react"
import { ArrowLeft, KeyRound, Loader2, UserRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useLogin, useMe } from "@/hooks/useNexora"
import { getErrorMessage } from "@/lib/utils"
import App from "@/App"
import { AuthLayout, AuthLoadingScreen } from "@/auth/AuthLayout"
import { PasswordChangeScreen } from "@/auth/PasswordChangeScreen"

export default function AuthGate() {
  const { data: user, isLoading } = useMe()
  const loginMutation = useLogin()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)

  if (isLoading) return <AuthLoadingScreen />
  if (user?.must_change_password) return <PasswordChangeScreen username={user.username} />
  if (user) return <App />

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await loginMutation.mutateAsync({ username: username.trim(), password })
      setPassword("")
    } catch (reason) {
      setError(getErrorMessage(reason, "فشل تسجيل الدخول. تحقق من البيانات وحاول مرة أخرى."))
    }
  }

  return (
    <AuthLayout title="مرحبًا بعودتك" description="سجّل الدخول بأمان لمتابعة الالتزام وإدارة التنبيهات في مواقعك." mode="light">
      <form className="space-y-4" onSubmit={submit}>
        <div className="space-y-1.5">
          <label htmlFor="username" className="text-sm font-semibold text-foreground">اسم المستخدم</label>
          <div className="relative">
            <UserRound className="pointer-events-none absolute end-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required maxLength={100} className="min-h-12 rounded-xl bg-background/70 pe-11" placeholder="أدخل اسم المستخدم" />
          </div>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="password" className="text-sm font-semibold text-foreground">كلمة المرور</label>
          <div className="relative">
            <KeyRound className="pointer-events-none absolute end-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="password" value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required maxLength={128} className="min-h-12 rounded-xl bg-background/70 pe-11" placeholder="أدخل كلمة المرور" />
          </div>
        </div>
        {error && <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive-light px-3 py-2.5 text-sm leading-5 text-destructive-foreground">{error}</p>}
        <Button className="min-h-12 w-full rounded-xl text-sm font-semibold shadow-sm" type="submit" disabled={loginMutation.isPending}>
          {loginMutation.isPending ? <><Loader2 className="size-4 animate-spin" /> جارٍ التحقق...</> : <>دخول إلى النظام <ArrowLeft className="size-4" /></>}
        </Button>
        <p className="pt-1 text-center text-xs text-muted-foreground">الوصول مخصص للحسابات التي أنشأها مسؤول النظام.</p>
      </form>
    </AuthLayout>
  )
}
