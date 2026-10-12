import type { ReactNode } from "react"

interface CardProps {
  children: ReactNode
  className?: string
  featured?: boolean
}

export default function Card({ children, className = "", featured = false }: CardProps) {
  return (
    <div
      className={`${
        featured ? "card-featured" : "card-premium border border-border/80"
      } text-card-foreground ${className}`}
    >
      {children}
    </div>
  )
}
