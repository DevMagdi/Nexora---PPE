import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, Loader2 } from "lucide-react"
import Brand from "@/components/Brand"
import { InlineError } from "@/components/Feedback"
import { Button } from "@/components/ui/button"
import { changePassword } from "@/lib/api"

export default function PasswordChangeScreen({ username }: { username: string }) {
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const client = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: async () => {
      setCurrent("")
      setNext("")
      setConfirm("")
      await client.invalidateQueries({ queryKey: ["me"] })
    },
  })
  return (
    <main
      className="flex min-h-dvh flex-col items-center justify-center gap-8 p-5"
      dir="rtl"
      lang="ar"
    >
      <Brand />
      <section className="panel w-full max-w-md p-7">
        <KeyRound className="mb-4 size-8 text-primary" strokeWidth={1.4} />
        <h1 className="text-2xl">تأمين حسابك</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          مرحباً {username}. غيّر كلمة المرور المؤقتة قبل دخول المنصة.
        </p>
        <form
          className="mt-6 space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            setError(null)
            if (next !== confirm) {
              setError("كلمتا المرور غير متطابقتين")
              return
            }
            mutation.mutate()
          }}
        >
          <div>
            <label htmlFor="current-password" className="field-label">
              كلمة المرور الحالية
            </label>
            <input
              id="current-password"
              className="field"
              type="password"
              autoComplete="current-password"
              required
              maxLength={128}
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="new-password" className="field-label">
              كلمة المرور الجديدة
            </label>
            <input
              id="new-password"
              className="field"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="confirm-password" className="field-label">
              تأكيد كلمة المرور
            </label>
            <input
              id="confirm-password"
              className="field"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <p className="notice">
            12 حرفاً على الأقل، بحروف كبيرة وصغيرة وأرقام ورمز خاص، دون اسم المستخدم أو كلمات سهلة
            التخمين.
          </p>
          <InlineError error={error || mutation.error} />
          <Button className="w-full" type="submit" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="animate-spin" />}حفظ ومتابعة
          </Button>
        </form>
      </section>
    </main>
  )
}
