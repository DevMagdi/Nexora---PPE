import { useEffect, useRef, useState } from "react"

export function useInView<T extends Element>() {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(() => typeof IntersectionObserver === "undefined")

  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (typeof IntersectionObserver === "undefined") return
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { rootMargin: "100px" })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [ref, inView] as const
}
