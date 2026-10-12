import { useCallback, useEffect, useRef, useState } from "react"
import { getWebSocketUrl } from "@/lib/api"
import { normalizeLiveCounts } from "@/lib/formatters"
import type { Camera, LiveCounts, LiveStatus } from "@/types"

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  )
  useEffect(() => {
    const mq = window.matchMedia(query)
    const onChange = () => setMatches(mq.matches)
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [query])
  return matches
}

export function useCountUp(target: number | undefined, duration = 700): number | undefined {
  const [value, setValue] = useState(0)
  const currentRef = useRef(0)
  useEffect(() => {
    if (target === undefined) return
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const start = currentRef.current
    const diff = target - start
    if (diff === 0 || reduceMotion) {
      currentRef.current = target
      setValue(target)
      return
    }
    const t0 = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const progress = Math.min((now - t0) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const next = Math.round(start + diff * eased)
      currentRef.current = next
      setValue(next)
      if (progress < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return target === undefined ? undefined : value
}

export function useInView<T extends Element>() {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => setInView(entry.isIntersecting),
      { rootMargin: "100px" },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return [ref, inView] as const
}

export function useTheme() {
  const [dark, setDark] = useState(() => {
    try {
      return localStorage.getItem("nexora-theme") === "dark"
    } catch {
      return false
    }
  })
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    try {
      localStorage.setItem("nexora-theme", dark ? "dark" : "light")
    } catch {
      /* التخزين غير متاح */
    }
  }, [dark])
  return [dark, setDark] as const
}

function areCountsEqual(a: LiveCounts, b: LiveCounts): boolean {
  return (
    a.hardhat === b.hardhat &&
    a.vest === b.vest &&
    a.person === b.person &&
    a.no_mask === b.no_mask &&
    a.no_gloves === b.no_gloves &&
    a.no_goggles === b.no_goggles &&
    a.no_cap === b.no_cap &&
    a.skin_hits === b.skin_hits &&
    a.total === b.total
  )
}

export function useLiveCameraSocket(selectedCamera: Camera | null) {
  const [counts, setCounts] = useState<LiveCounts>({})
  const [liveStatus, setLiveStatus] = useState<LiveStatus>("idle")
  const [streamLive, setStreamLive] = useState(false)

  const handleStreamReady = useCallback(() => setStreamLive(true), [])
  const handleStreamLost = useCallback(() => {
    setStreamLive(false)
    setLiveStatus((prev) => (prev === "open" ? "reconnecting" : prev))
  }, [])

  useEffect(() => {
    if (!selectedCamera?.is_running) {
      return
    }
    const camId = selectedCamera.id
    let ws: WebSocket | null = null
    let reconnectTimer = 0
    let connectionTimer = 0
    let attempts = 0
    let disposed = false

    const connect = () => {
      if (disposed) return
      setLiveStatus(attempts ? "reconnecting" : "connecting")
      const socket = new WebSocket(getWebSocketUrl(camId))
      ws = socket
      connectionTimer = window.setTimeout(() => {
        if (socket.readyState === WebSocket.CONNECTING) socket.close()
      }, 10_000)

      socket.onopen = () => {
        window.clearTimeout(connectionTimer)
        if (disposed) {
          socket.close()
          return
        }
        attempts = 0
        setLiveStatus("open")
      }
      socket.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data)
          const next = normalizeLiveCounts(d)
          if (next) {
            setCounts((prev) => (areCountsEqual(prev, next) ? prev : next))
          }
        } catch {
          /* رسالة غير صالحة */
        }
      }
      socket.onerror = () => socket.close()
      socket.onclose = () => {
        window.clearTimeout(connectionTimer)
        if (disposed) return
        setLiveStatus("reconnecting")
        attempts++
        reconnectTimer = window.setTimeout(connect, Math.min(1000 * 2 ** attempts, 15_000))
      }
    }
    connect()
    return () => {
      disposed = true
      window.clearTimeout(reconnectTimer)
      window.clearTimeout(connectionTimer)
      ws?.close()
      setCounts({})
      setStreamLive(false)
      setLiveStatus("idle")
    }
  }, [selectedCamera?.id, selectedCamera?.is_running])

  const activeCounts = selectedCamera?.is_running ? counts : {}
  const activeLiveStatus: LiveStatus = !selectedCamera?.is_running
    ? "idle"
    : streamLive
      ? "open"
      : liveStatus === "open"
        ? "connecting"
        : liveStatus

  return {
    counts: activeCounts,
    activeLiveStatus,
    handleStreamReady,
    handleStreamLost,
  }
}
