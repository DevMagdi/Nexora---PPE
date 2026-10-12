import { useEffect, useState } from "react"
import { getWebSocketUrl } from "@/lib/api"
import { normalizeLiveCounts } from "@/lib/domain"
import type { LiveCounts, LiveStatus } from "@/types/app"

type Snapshot = { key: string; counts: LiveCounts; status: LiveStatus }

export function useLiveCounts(cameraId: number | undefined, isRunning: boolean, generation = 0) {
  const key = `${cameraId ?? "none"}-${isRunning}-${generation}`
  const [snapshot, setSnapshot] = useState<Snapshot>({ key: "", counts: {}, status: "idle" })

  useEffect(() => {
    if (cameraId === undefined || !isRunning) return

    let socket: WebSocket | null = null
    let reconnectTimer = 0
    let connectionTimer = 0
    let attempts = 0
    let disposed = false

    const update = (status: LiveStatus, counts?: LiveCounts) => {
      setSnapshot((previous) => ({
        key,
        status,
        counts: counts ?? (previous.key === key ? previous.counts : {}),
      }))
    }

    const connect = () => {
      if (disposed) return
      update(attempts > 0 ? "reconnecting" : "connecting")

      try {
        const nextSocket = new WebSocket(getWebSocketUrl(cameraId))
        socket = nextSocket
        connectionTimer = window.setTimeout(() => {
          if (nextSocket.readyState === WebSocket.CONNECTING) nextSocket.close()
        }, 10_000)

        nextSocket.onopen = () => {
          window.clearTimeout(connectionTimer)
          if (disposed) {
            nextSocket.close()
            return
          }
          attempts = 0
          update("open")
        }
        nextSocket.onmessage = (event) => {
          try {
            const parsed: unknown = JSON.parse(event.data)
            const next = normalizeLiveCounts(parsed)
            if (!disposed && next) update("open", next)
          } catch {
            // Ignore malformed frames while preserving the current connection.
          }
        }
        nextSocket.onerror = () => nextSocket.close()
        nextSocket.onclose = () => {
          window.clearTimeout(connectionTimer)
          if (disposed) return
          update("reconnecting")
          attempts += 1
          reconnectTimer = window.setTimeout(connect, Math.min(1000 * 2 ** attempts, 15_000))
        }
      } catch {
        if (disposed) return
        update("reconnecting")
        attempts += 1
        reconnectTimer = window.setTimeout(connect, Math.min(1000 * 2 ** attempts, 15_000))
      }
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(reconnectTimer)
      window.clearTimeout(connectionTimer)
      socket?.close()
    }
  }, [cameraId, isRunning, key])

  if (cameraId === undefined || !isRunning) return { counts: {}, status: "idle" as const }
  if (snapshot.key !== key) return { counts: {}, status: "connecting" as const }
  return { counts: snapshot.counts, status: snapshot.status }
}
