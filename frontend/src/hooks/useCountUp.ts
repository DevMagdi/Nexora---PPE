import { useEffect, useRef, useState } from "react"

export function useCountUp(target: number | undefined, duration = 700) {
  const [value, setValue] = useState<number | undefined>(undefined)
  const currentRef = useRef(target ?? 0)

  useEffect(() => {
    if (target === undefined) return
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const start = currentRef.current
    const difference = target - start
    if (difference === 0 || reduceMotion) {
      currentRef.current = target
      setValue(target)
      return
    }

    const startedAt = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const progress = Math.min((now - startedAt) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const next = Math.round(start + difference * eased)
      currentRef.current = next
      setValue(next)
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration])

  return target === undefined ? undefined : value
}
