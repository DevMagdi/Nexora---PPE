import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { KeyRound, Loader2, Plus, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ErrorPanel, InlineError, Loading } from "@/components/Feedback"
import Modal from "@/components/Modal"
import { useUsers } from "@/hooks/useNexora"
import { createUser, resetUserPassword, updateUser } from "@/lib/api"
import { ROLE_LABEL, formatDate } from "@/lib/formatters"
import type { IssuedAccount, UserAccount } from "@/types"

export default function UsersPage({ refresh }: { refresh: () => Promise<void> }) {
  const query = useUsers()
  const [open, setOpen] = useState(false)
  const [username, setUsername] = useState("")
  const [role, setRole] = useState<"supervisor" | "viewer">("viewer")
  const [issued, setIssued] = useState<IssuedAccount | null>(null)
  const [reset, setReset] = useState<UserAccount | null>(null)
  const create = useMutation({
    mutationFn: () => createUser(username, role),
    onSuccess: async (data) => {
      setOpen(false)
      setUsername("")
      setIssued(data)
      await refresh()
    },
  })
  const update = useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number
      role?: "supervisor" | "viewer"
      is_active?: boolean
    }) => updateUser(id, body),
    onSuccess: refresh,
  })
  const password = useMutation({
    mutationFn: (id: number) => resetUserPassword(id),
    onSuccess: async (data) => {
      setReset(null)
      setIssued(data)
      await refresh()
    },
  })
  if (query.isPending) return <Loading />
  if (query.isError) return <ErrorPanel error={query.error} retry={() => void query.refetch()} />
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-xs leading-relaxed text-muted-foreground">
          المدير يدير النظام، المشرف يشغّل المصادر ويعالج التنبيهات، والمشاهد للقراءة فقط.
        </p>
        <Button
          onClick={() => {
            create.reset()
            setOpen(true)
          }}
        >
          <Plus />
          إضافة مستخدم
        </Button>
      </div>
      <InlineError error={update.error} />
      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="event-table">
            <thead>
              <tr>
                <th scope="col">المستخدم</th>
                <th scope="col">الدور</th>
                <th scope="col">الحالة</th>
                <th scope="col">تاريخ الإنشاء</th>
                <th scope="col">الوصول</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((user) => (
                <tr key={user.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <span className="metric-icon !size-8">
                        <ShieldCheck />
                      </span>
                      <span className="latin text-xs">{user.username}</span>
                    </div>
                  </td>
                  <td>
                    {user.role === "admin" ? (
                      <span className="badge">{ROLE_LABEL.admin}</span>
                    ) : (
                      <select
                        className="field !h-9 min-w-32"
                        aria-label={`دور ${user.username}`}
                        value={user.role}
                        disabled={update.isPending}
                        onChange={(e) =>
                          update.mutate({
                            id: user.id,
                            role: e.target.value as "supervisor" | "viewer",
                          })
                        }
                      >
                        <option value="supervisor">{ROLE_LABEL.supervisor}</option>
                        <option value="viewer">{ROLE_LABEL.viewer}</option>
                      </select>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${user.is_active ? "badge-success" : ""}`}>
                      <span className="status-dot" />
                      {user.is_active ? "نشط" : "معطّل"}
                    </span>
                    {user.must_change_password && (
                      <p className="mt-2 text-[10px] text-muted-foreground">
                        تغيير كلمة المرور مطلوب
                      </p>
                    )}
                  </td>
                  <td className="text-muted-foreground">{formatDate(user.created_at)}</td>
                  <td>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          password.reset()
                          setReset(user)
                        }}
                      >
                        <KeyRound />
                        إعادة تعيين
                      </Button>
                      {user.role !== "admin" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={update.isPending}
                          onClick={() => update.mutate({ id: user.id, is_active: !user.is_active })}
                        >
                          {user.is_active ? "تعطيل" : "تفعيل"}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-[10px] text-muted-foreground">
        إنشاء مدير إضافي محصور بأداة إدارة الحسابات المحلية. تغيير الدور أو تعطيل الحساب يلغي جلساته
        الحالية.
      </p>
      <Modal
        open={open}
        onClose={() => {
          if (!create.isPending) setOpen(false)
        }}
        title="إصدار حساب جديد"
        description="تُولّد كلمة مرور مؤقتة ويُلزم المستخدم بتغييرها عند أول دخول."
      >
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate()
          }}
        >
          <div>
            <label className="field-label" htmlFor="new-username">
              اسم المستخدم
            </label>
            <input
              id="new-username"
              dir="ltr"
              className="field latin"
              value={username}
              required
              minLength={3}
              maxLength={100}
              pattern="[A-Za-z0-9_.\-]+"
              onChange={(e) => setUsername(e.target.value)}
              placeholder="safety.supervisor"
            />
          </div>
          <div>
            <label className="field-label" htmlFor="new-role">
              الدور
            </label>
            <select
              id="new-role"
              className="field"
              value={role}
              onChange={(e) => setRole(e.target.value as typeof role)}
            >
              <option value="viewer">مشاهد</option>
              <option value="supervisor">مشرف السلامة</option>
            </select>
          </div>
          <InlineError error={create.error} />
          <Button className="w-full" type="submit" disabled={create.isPending}>
            {create.isPending && <Loader2 />}إصدار الحساب
          </Button>
        </form>
      </Modal>
      <Modal
        open={reset !== null}
        onClose={() => {
          if (!password.isPending) setReset(null)
        }}
        title="إعادة تعيين كلمة المرور"
        description={`سيتم إلغاء جميع جلسات «${reset?.username ?? ""}» وإصدار كلمة مرور مؤقتة جديدة.`}
      >
        <InlineError error={password.error} />
        <Button
          disabled={password.isPending}
          onClick={() => {
            if (reset) password.mutate(reset.id)
          }}
        >
          {password.isPending && <Loader2 />}تأكيد إعادة التعيين
        </Button>
      </Modal>
      <Modal
        open={issued !== null}
        onClose={() => {
          setIssued(null)
          create.reset()
          password.reset()
        }}
        title="بيانات الدخول المؤقتة"
        description="تظهر كلمة المرور مرة واحدة هنا. سلّمها للمستخدم عبر قناة آمنة قبل إغلاق النافذة."
      >
        {issued && (
          <>
            <p className="text-xs text-muted-foreground">
              اسم المستخدم: <span className="latin text-foreground">{issued.username}</span>
            </p>
            <code
              className="block select-all break-all rounded-lg border border-border bg-muted p-4 text-center text-sm text-muted-foreground"
              dir="ltr"
            >
              {issued.initial_password}
            </code>
            <p className="notice">
              سيُطلب تغيير كلمة المرور فور تسجيل الدخول. لا تشارك هذه البيانات في قنوات عامة.
            </p>
            <Button
              onClick={() => {
                setIssued(null)
                create.reset()
                password.reset()
              }}
            >
              تم تسليم البيانات بأمان
            </Button>
          </>
        )}
      </Modal>
    </div>
  )
}
