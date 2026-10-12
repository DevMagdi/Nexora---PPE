import { useState } from "react"
import { ShieldCheck } from "lucide-react"
import nexoraLogoColor from "@/assets/logo/nexora-logo-full-color.svg"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useChangePassword } from "@/hooks/useNexora"
import { getErrorMessage } from "@/lib/utils"

interface PasswordChangeScreenProps {
  username: string
}

export default function PasswordChangeScreen({ username }: PasswordChangeScreenProps) {
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
