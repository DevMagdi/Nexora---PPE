import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Factory, Loader2, MapPin, Pencil, Plus, Save, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Empty, InlineError } from "@/components/Feedback"
import Modal from "@/components/Modal"
import { createSite, deleteSite, updateSite } from "@/lib/api"
import { SITE_LABEL, num } from "@/lib/formatters"
import type { Camera, Site, SiteKind } from "@/types"

function SiteForm({ site, onSuccess }: { site?: Site; onSuccess: () => void }) {
  const [name, setName] = useState(site?.name ?? "")
  const [kind, setKind] = useState<SiteKind>(site?.kind ?? "factory")
  const [location, setLocation] = useState(site?.location ?? "")
  const mutation = useMutation({
    mutationFn: () =>
      site ? updateSite(site.id, { name, kind, location }) : createSite({ name, kind, location }),
    onSuccess,
  })
  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <div>
        <label className="field-label" htmlFor="site-name">
          اسم المصنع أو الموقع
        </label>
        <input
          id="site-name"
          className="field"
          required
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="مثال: مصنع المنطقة الصناعية"
        />
      </div>
      <div>
        <label className="field-label" htmlFor="site-kind">
          نوع الموقع الصناعي
        </label>
        <select
          id="site-kind"
          className="field"
          value={kind}
          onChange={(e) => setKind(e.target.value as SiteKind)}
        >
          {Object.entries(SITE_LABEL).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="field-label" htmlFor="site-location">
          الموقع / العنوان
        </label>
        <input
          id="site-location"
          className="field"
          maxLength={200}
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="المدينة · المنطقة · المبنى"
        />
      </div>
      <InlineError error={mutation.error} />
      <Button className="w-full" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? <Loader2 /> : <Save />}حفظ الموقع
      </Button>
    </form>
  )
}
export default function SitesPage({
  sites,
  cameras,
  isAdmin,
  refresh,
}: {
  sites: Site[]
  cameras: Camera[]
  isAdmin: boolean
  refresh: () => Promise<void>
}) {
  const [form, setForm] = useState<Site | "new" | null>(null)
  const [target, setTarget] = useState<Site | null>(null)
  const remove = useMutation({
    mutationFn: (id: number) => deleteSite(id),
    onSuccess: async () => {
      setTarget(null)
      await refresh()
    },
  })
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">{num(sites.length)} مصنع وموقع صناعي</p>
        {isAdmin && (
          <Button onClick={() => setForm("new")}>
            <Plus />
            إضافة موقع
          </Button>
        )}
      </div>
      {!sites.length ? (
        <div className="panel">
          <Empty
            title="منظور واحد لكل مواقعك"
            description="أضف مصانعك ومواقع الإنشاء والورش والمستودعات، ثم اربط الكاميرات بها من إعدادات المصدر."
          />
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {sites.map((site) => (
            <article key={site.id} className="panel p-6">
              <div className="mb-5 flex items-center justify-between">
                <span className="metric-icon">
                  <Factory />
                </span>
                <span className="badge">{SITE_LABEL[site.kind]}</span>
              </div>
              <h2 className="text-base">{site.name}</h2>
              <p className="mt-3 flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
                <MapPin className="mt-0.5 size-3.5 shrink-0" />
                {site.location || "العنوان غير محدد"}
              </p>
              <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
                <span className="text-xs text-muted-foreground">
                  {num(cameras.filter((camera) => camera.site_id === site.id).length)} كاميرا مرتبطة
                </span>
                {isAdmin && (
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`تعديل ${site.name}`}
                      onClick={() => setForm(site)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`حذف ${site.name}`}
                      onClick={() => {
                        remove.reset()
                        setTarget(site)
                      }}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      <Modal
        open={form !== null}
        onClose={() => setForm(null)}
        title={form === "new" ? "إضافة موقع صناعي" : "تعديل الموقع"}
        description="إعداد المصانع ومواقع العمل ضمن النطاق الصناعي فقط."
      >
        {form && (
          <SiteForm
            key={form === "new" ? "new" : form.id}
            site={form === "new" ? undefined : form}
            onSuccess={() => {
              setForm(null)
              void refresh()
            }}
          />
        )}
      </Modal>
      <Modal
        open={target !== null}
        onClose={() => {
          if (!remove.isPending) setTarget(null)
        }}
        title="حذف الموقع"
        description={`تأكيد حذف «${target?.name ?? ""}». يجب إعادة تعيين الكاميرات المرتبطة قبل الحذف.`}
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
            {remove.isPending && <Loader2 />}حذف الموقع
          </Button>
        </div>
      </Modal>
    </div>
  )
}
