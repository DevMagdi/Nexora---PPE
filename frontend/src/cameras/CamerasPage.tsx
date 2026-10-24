import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Cctv, Loader2, Pencil, Play, Plus, Search, Square, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Empty, InlineError } from "@/components/Feedback"
import Modal from "@/components/Modal"
import CameraForm from "@/cameras/CameraForm"
import { CONNECTION_LABEL, SOURCE_LABEL, sourceIsBusy } from "@/cameras/sources"
import { getErrorMessage } from "@/lib/utils"
import { deleteCamera, startCamera, stopCamera } from "@/lib/api"
import { RULE_LABEL, num } from "@/lib/formatters"
import type { Camera, Site, SystemMeta } from "@/types"

export default function CamerasPage({
  cameras,
  sites,
  meta,
  canOperate,
  onLive,
  refresh,
  notify,
}: {
  cameras: Camera[]
  sites: Site[]
  meta?: SystemMeta
  canOperate: boolean
  onLive: (id: number) => void
  refresh: () => Promise<void>
  notify: (message: string, error?: boolean) => void
}) {
  const [query, setQuery] = useState("")
  const [form, setForm] = useState<Camera | "new" | null>(null)
  const [target, setTarget] = useState<Camera | null>(null)
  const toggle = useMutation({
    mutationFn: (camera: Camera) =>
      sourceIsBusy(camera) ? stopCamera(camera.id) : startCamera(camera.id),
    onSuccess: async () => {
      await refresh()
      notify("تم تحديث حالة الكاميرا")
    },
    onError: async (error) => {
      notify(getErrorMessage(error, "تعذّر تشغيل المصدر"), true)
      await refresh()
    },
  })
  const remove = useMutation({
    mutationFn: (id: number) => deleteCamera(id),
    onSuccess: async () => {
      setTarget(null)
      await refresh()
      notify("تم حذف الكاميرا")
    },
  })
  const list = cameras.filter((item) =>
    `${item.name} ${sites.find((site) => site.id === item.site_id)?.name ?? ""}`.includes(query),
  )
  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="absolute start-3 top-3.5 size-4 text-muted-foreground" />
          <input
            className="field ps-10"
            aria-label="البحث في الكاميرات"
            placeholder="ابحث عن كاميرا أو موقع…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">{num(cameras.length)} كاميرا</span>
          {canOperate && (
            <Button onClick={() => setForm("new")}>
              <Plus />
              إضافة كاميرا
            </Button>
          )}
        </div>
      </div>
      {!list.length ? (
        <div className="panel">
          <Empty
            title={query ? "لا توجد نتائج" : "ابدأ بأول مصدر للمراقبة"}
            description={
              query
                ? "جرّب اسم كاميرا أو موقع آخر."
                : "أضف كاميرا RTSP من شبكة الموقع، أو ارفع مقطع فيديو من صفحة التحليل."
            }
            action={
              canOperate && !query ? (
                <Button variant="outline" onClick={() => setForm("new")}>
                  <Plus />
                  إضافة مصدر كاميرا
                </Button>
              ) : undefined
            }
          />
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((camera) => (
            <article key={camera.id} className="panel overflow-hidden">
              <div className="camera-preview">
                <Cctv />
                <span
                  className={`badge absolute start-4 top-4 ${camera.connection_status === "error" ? "badge-danger" : camera.is_running ? "badge-success" : ""}`}
                >
                  <span className="status-dot" />
                  {CONNECTION_LABEL[camera.connection_status] ??
                    (camera.is_running ? "متصلة" : "متوقفة")}
                </span>
                <span className="latin absolute bottom-4 end-4 text-[9px] text-muted-foreground">
                  CAM-{String(camera.id).padStart(3, "0")}
                </span>
              </div>
              <div className="p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm">{camera.name}</h2>
                    <p className="mt-1.5 text-[11px] text-muted-foreground">
                      {sites.find((site) => site.id === camera.site_id)?.name ?? "موقع غير معيّن"}
                    </p>
                  </div>
                  <span className="badge latin text-[9px]">{SOURCE_LABEL[camera.source_type]}</span>
                </div>
                <div
                  className="latin my-5 truncate rounded-lg bg-muted p-3 text-[10px] text-muted-foreground"
                  dir="ltr"
                >
                  {camera.source_uri}
                </div>
                {camera.last_error && (
                  <p className="notice notice-error mb-5" role="alert">
                    {camera.last_error}
                  </p>
                )}
                {camera.source_type === "usb" && (
                  <p className="source-help mb-5">
                    USB محلي — تطوير وتجربة فقط، غير مسموح للإنتاج.
                  </p>
                )}
                <div className="mb-5 flex flex-wrap gap-1.5">
                  {camera.enabled_classes.map((key) => (
                    <span
                      key={key}
                      className="text-[10px] text-muted-foreground after:ms-1.5 after:text-muted-foreground after:content-['·'] last:after:content-none"
                    >
                      {RULE_LABEL[key]}
                    </span>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2 border-t border-border pt-5">
                  <Button
                    variant={camera.is_running ? "default" : "outline"}
                    size="sm"
                    className="flex-1"
                    onClick={() => onLive(camera.id)}
                  >
                    المراقبة
                  </Button>
                  {canOperate && (
                    <>
                      <Button
                        variant="outline"
                        size="icon"
                        aria-label={`${sourceIsBusy(camera) ? "إيقاف" : "تشغيل"} ${camera.name}`}
                        disabled={toggle.isPending}
                        onClick={() => toggle.mutate(camera)}
                      >
                        {toggle.isPending && toggle.variables?.id === camera.id ? (
                          <Loader2 />
                        ) : sourceIsBusy(camera) ? (
                          <Square />
                        ) : (
                          <Play />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`تعديل ${camera.name}`}
                        onClick={() => setForm(camera)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`حذف ${camera.name}`}
                        onClick={() => setTarget(camera)}
                      >
                        <Trash2 />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      <Modal
        open={form !== null}
        onClose={() => setForm(null)}
        title={form === "new" ? "إضافة مصدر كاميرا" : "إعدادات الكاميرا"}
        description="اختر نوع المصدر أولًا. RTSP هو الافتراضي للإنتاج؛ ملف الفيديو وUSB للتجربة."
      >
        {form && (
          <CameraForm
            key={form === "new" ? "new" : form.id}
            camera={form === "new" ? undefined : form}
            sites={sites}
            meta={meta}
            onSuccess={() => {
              setForm(null)
              void refresh()
              notify("تم حفظ إعدادات الكاميرا")
            }}
          />
        )}
      </Modal>
      <Modal
        open={target !== null}
        onClose={() => {
          if (!remove.isPending) setTarget(null)
        }}
        title="تأكيد حذف الكاميرا"
        description={`سيتم إيقاف «${target?.name ?? ""}» وحذف سجل أحداثها المرتبط. لا يمكن التراجع عن هذا الإجراء.`}
      >
        <InlineError error={remove.error} />
        <div className="flex justify-end gap-2">
          <Button variant="outline" disabled={remove.isPending} onClick={() => setTarget(null)}>
            إلغاء
          </Button>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() => {
              if (target) remove.mutate(target.id)
            }}
          >
            {remove.isPending && <Loader2 />}تأكيد الحذف
          </Button>
        </div>
      </Modal>
    </div>
  )
}
