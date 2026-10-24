import {
  Cctv,
  Factory,
  FileClock,
  LayoutDashboard,
  Radio,
  ScanLine,
  ShieldCheck,
  UsersRound,
} from "lucide-react"
import Brand from "@/components/Brand"
import Modal from "@/components/Modal"
import { TAB_TITLES } from "@/lib/formatters"
import type { SystemMeta, TabKey, UserRole } from "@/types"

const OPERATIONS = [
  { key: "overview", icon: LayoutDashboard },
  { key: "live", icon: Radio },
  { key: "cameras", icon: Cctv },
  { key: "uploads", icon: ScanLine },
] as const
const MANAGEMENT = [
  { key: "violations", icon: FileClock },
  { key: "sites", icon: Factory },
  { key: "users", icon: UsersRound },
] as const
interface Props {
  tab: TabKey
  onNavigate: (tab: TabKey) => void
  role: UserRole
  model?: SystemMeta
  open: boolean
  onClose: () => void
}

function Navigation({ tab, onNavigate, role, model }: Omit<Props, "open" | "onClose">) {
  return (
    <>
      <div className="sidebar-brand">
        <Brand />
      </div>
      <nav aria-label="التنقل الرئيسي">
        <div className="nav-caption">غرفة العمليات</div>
        {OPERATIONS.filter((item) => item.key !== "uploads" || role !== "viewer").map((item) => (
          <button
            key={item.key}
            className="nav-item"
            aria-current={tab === item.key ? "page" : undefined}
            onClick={() => onNavigate(item.key)}
          >
            <item.icon />
            <span>{TAB_TITLES[item.key]}</span>
          </button>
        ))}
        <div className="nav-caption mt-7">المتابعة والإدارة</div>
        {MANAGEMENT.filter((item) => item.key !== "users" || role === "admin").map((item) => (
          <button
            key={item.key}
            className="nav-item"
            aria-current={tab === item.key ? "page" : undefined}
            onClick={() => onNavigate(item.key)}
          >
            <item.icon />
            <span>{TAB_TITLES[item.key]}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="mb-2 flex items-center gap-2 text-[11px] text-muted-foreground">
            <ShieldCheck className="size-4" />
            نظام صناعي موحّد
          </div>
          <div dir="ltr" className="latin break-all text-[9px] text-muted-foreground">
            {model?.model ?? "جارٍ قراءة إعدادات الموديل…"}
          </div>
          <div className="mt-2 text-[10px] text-muted-foreground">
            حد الثقة:{" "}
            <span className="latin text-muted-foreground">
              {model ? `${Math.round(model.confidence * 100)}%` : "—"}
            </span>{" "}
            · استدلال محلي
          </div>
        </div>
        <p className="eyebrow mt-4 !text-[8px] !text-muted-foreground" dir="ltr">
          SAFETY IS AN OPERATING STANDARD.
        </p>
      </div>
    </>
  )
}
export default function Sidebar(props: Props) {
  const navigate = (tab: TabKey) => {
    props.onNavigate(tab)
    props.onClose()
  }
  return (
    <>
      <aside className="sidebar">
        <Navigation {...props} onNavigate={navigate} />
      </aside>
      <Modal
        open={props.open}
        onClose={props.onClose}
        title="قائمة التنقل"
        description="منصة السلامة الصناعية"
      >
        <div className="flex max-h-[65vh] flex-col overflow-auto">
          <Navigation {...props} onNavigate={navigate} />
        </div>
      </Modal>
    </>
  )
}
