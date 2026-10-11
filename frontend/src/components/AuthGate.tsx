import { useState } from "react"
import App from "@/App"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useLogin, useMe } from "@/hooks/useNexora"
import { getErrorMessage } from "@/lib/utils"
import { getToken, clearToken } from "@/lib/api"

export default function AuthGate() {
  const token = getToken()
  const { data: me, isLoading } = useMe()
  const loginMut = useLogin()

  const [username, setUsername] = useState("admin")
  const [password, setPassword] = useState("admin123")
  const [err, setErr] = useState<string | null>(null)

  // لو عندنا token + me -> افتح التطبيق
  if (token && me) return <App />

  async function onLogin(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    try {
      await loginMut.mutateAsync({ username, password })
    } catch (e) {
      setErr(getErrorMessage(e, "فشل تسجيل الدخول"))
      clearToken()
    }
  }

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background p-6" dir="rtl">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl">
        <div className="text-xl font-bold">تسجيل الدخول</div>
        <div className="mt-1 text-sm text-muted-foreground">أدخل بيانات الحساب للوصول للوحة Nexora.</div>

        <form className="mt-6 space-y-3" onSubmit={onLogin}>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username" required />
          <Input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" type="password" required />

          <Button className="w-full" type="submit" disabled={loginMut.isPending || isLoading}>
            {loginMut.isPending ? "جارٍ تسجيل الدخول..." : "دخول"}
          </Button>

          {err && <div className="text-sm text-destructive">{err}</div>}

          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              clearToken()
              window.location.reload()
            }}
          >
            مسح الجلسة
          </Button>
        </form>
      </div>
    </div>
  )
}