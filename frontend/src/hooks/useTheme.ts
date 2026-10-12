import { useEffect, useState } from "react"

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
      // Storage may be unavailable in locked-down browser contexts.
    }
  }, [dark])

  return [dark, setDark] as const
}
