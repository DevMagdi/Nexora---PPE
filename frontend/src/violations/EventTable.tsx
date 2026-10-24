import { CheckCheck, Image, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Empty } from "@/components/Feedback"
import { classLabel, formatDate, formatTime } from "@/lib/formatters"
import type { Camera, Violation } from "@/types"

export default function EventTable({
  items,
  cameras,
  canOperate,
  pendingId,
  onResolve,
  onEvidence,
}: {
  items: Violation[]
  cameras: Camera[]
  canOperate: boolean
  pendingId?: number
  onResolve: (id: number) => void
  onEvidence: (item: Violation) => void
}) {
  if (!items.length)
    return (
      <Empty
        title="لا توجد أحداث في هذه الفترة"
        description="ستظهر المخالفات الصناعية هنا بعد رصد دليل مستمر من الكاميرات. لا تعني القائمة الفارغة قياس نسبة الالتزام."
      />
    )
  return (
    <div className="overflow-x-auto">
      <table className="event-table">
        <thead>
          <tr>
            <th scope="col">الحدث</th>
            <th scope="col">المصدر</th>
            <th scope="col">التوقيت</th>
            <th scope="col">الثقة</th>
            <th scope="col">الحالة</th>
            <th scope="col">الإجراء</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <div className="flex items-center gap-2.5">
                  <span
                    className={`h-7 w-0.5 rounded-full ${item.is_resolved ? "bg-success" : "bg-destructive"}`}
                  />
                  <div className="font-medium text-foreground">
                    {classLabel(item.violation_type)}
                    <span className="latin mt-1 block text-[9px] text-muted-foreground">
                      EVT-{String(item.id).padStart(5, "0")}
                    </span>
                  </div>
                </div>
              </td>
              <td>
                {cameras.find((camera) => camera.id === item.camera_id)?.name ??
                  `كاميرا ${item.camera_id}`}
              </td>
              <td>
                <div>{formatTime(item.timestamp)}</div>
                <div className="mt-1 text-[10px] text-muted-foreground">
                  {formatDate(item.timestamp)}
                </div>
              </td>
              <td className="latin">{Math.round(item.confidence * 100)}%</td>
              <td>
                <span className={`badge ${item.is_resolved ? "badge-success" : "badge-danger"}`}>
                  <span className="status-dot" />
                  {item.is_resolved ? "تمت المعالجة" : "مفتوحة"}
                </span>
              </td>
              <td>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={!item.frame_url}
                    onClick={() => onEvidence(item)}
                    aria-label={`عرض دليل الحدث ${item.id}`}
                  >
                    <Image />
                  </Button>
                  {canOperate && !item.is_resolved && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={pendingId !== undefined}
                      onClick={() => onResolve(item.id)}
                    >
                      {pendingId === item.id ? <Loader2 /> : <CheckCheck />}
                      معالجة
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
