import { useEffect, useState } from "react"
import { getWebSocketUrl, refreshMediaSession } from "@/lib/api"
import { normalizeLiveCounts } from "@/lib/formatters"
import type { LiveCounts } from "@/types"

export default function useLiveCamera(
  cameraId: number | undefined,
  running: boolean,
  attempt: number,
) {
  const [state, setState] = useState<{ id?: number; counts: LiveCounts | null; status: string }>({
    counts: null,
    status: "غير متصل",
  })
  useEffect(() => {
    if (cameraId === undefined || !running) return
    let socket: WebSocket | undefined
    let timer: ReturnType<typeof setTimeout> | undefined
    let disposed = false
    let lastMessage = 0
    async function connect() {
      try {
        await refreshMediaSession()
        if (disposed) return
        socket = new WebSocket(getWebSocketUrl(cameraId!))
        socket.onopen = () => {
          if (!disposed) setState({ id: cameraId, counts: null, status: "مباشر" })
        }
        socket.onmessage = (event) => {
          if (disposed) return
          try {
            const counts = normalizeLiveCounts(JSON.parse(event.data))
            if (counts) {
              lastMessage = Date.now()
              setState({ id: cameraId, counts, status: "مباشر" })
            }
          } catch {
            /* Invalid telemetry never becomes a UI count. */
          }
        }
        socket.onclose = () => {
          if (!disposed) {
            setState({ id: cameraId, counts: null, status: "إعادة الاتصال…" })
            timer = setTimeout(() => void connect(), 3000)
          }
        }
        socket.onerror = () => socket?.close()
      } catch {
        if (!disposed) {
          setState({ id: cameraId, counts: null, status: "تعذّر الاتصال" })
          timer = setTimeout(() => void connect(), 5000)
        }
      }
    }
    void connect()
    const stale = setInterval(() => {
      if (lastMessage && Date.now() - lastMessage > 15_000)
        setState({ id: cameraId, counts: null, status: "بانتظار إطارات حديثة" })
    }, 3000)
    const renew = setInterval(() => {
      void refreshMediaSession().catch(() => socket?.close())
    }, 8 * 60_000)
    return () => {
      disposed = true
      clearTimeout(timer)
      clearInterval(stale)
      clearInterval(renew)
      socket?.close()
    }
  }, [cameraId, running, attempt])
  return running
    ? state.id === cameraId
      ? state
      : { counts: null, status: "جارٍ الاتصال…" }
    : { counts: null, status: "متوقفة" }
}
