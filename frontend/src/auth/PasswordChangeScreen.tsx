import { useState } from "react"
import { Loader2, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useChangePassword } from "@/hooks/useNexora"
import { getErrorMessage } from "@/lib/utils"
import { AuthLayout } from "@/auth/AuthLayout"

export function PasswordChangeScreen({ username }: { username: string }) {
  const mutation = useChangePassword()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    if (newPassword !== confirmPassword) {
      setError("كلمتا المرور الجديدتان غير متطابقتين")
      return
    }
    try {
      await mutation.mutateAsync({ currentPassword, newPassword })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (reason) {
      setError(getErrorMessage(reason, "تعذّر تغيير كلمة المرور"))
    }
  }

  return (
    <AuthLayout title="تعيين كلمة مرور جديدة" description={`مرحبًا ${username}، يلزم تحديث كلمة المرور المؤقتة قبل استخدام النظام.`}>
      <div className="mb-4 flex items-center gap-2 rounded-xl border border-primary/15 bg-primary-light/60 p-3 text-sm text-primary">
        <ShieldCheck className="size-4 shrink-0" />
        <span>هذه الخطوة تحمي حسابك وتفعّل الوصول الكامل إلى لوحة المراقبة.</span>
      </div>
      <form className="space-y-4" onSubmit={submit}>
        <Field label="كلمة المرور المؤقتة الحالية" id="current-password">
          <Input id="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required maxLength={128} className="min-h-12 rounded-xl" />
        </Field>
        <Field label="كلمة المرور الجديدة" id="new-password">
          <Input id="new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" required minLength={12} maxLength={128} className="min-h-12 rounded-xl" />
        </Field>
        <Field label="تأكيد كلمة المرور الجديدة" id="confirm-password">
          <Input id="confirm-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" required minLength={12} maxLength={128} className="min-h-12 rounded-xl" />
        </Field>
        <p className="text-xs leading-5 text-muted-foreground">استخدم 12 حرفًا على الأقل وثلاثة أنواع من الأحرف، ولا تستخدم كلمة مرور من حرف واحد مكرّر أو تتضمن اسم المستخدم.</p>
        {error && <p id="password-error" role="alert" className="rounded-xl border border-destructive/20 bg-destructive-light px-3 py-2.5 text-sm text-destructive-foreground">{error}</p>}
        <Button className="min-h-12 w-full rounded-xl text-sm" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? <><Loader2 className="size-4 animate-spin" /> جارٍ التحديث...</> : "حفظ كلمة المرور والمتابعة"}
        </Button>
      </form>
    </AuthLayout>
  )
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return <div className="space-y-1.5"><label htmlFor={id} className="text-sm font-semibold text-foreground">{label}</label>{children}</div>
}
