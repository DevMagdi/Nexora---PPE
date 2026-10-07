// ── Health ───────────────────────────────────────────────────────
export type HealthResponse = {
  status: "ok" | "degraded" | string
  model_loaded: boolean
  cameras_active: number
}

// ── PPE Classes Meta ─────────────────────────────────────────────
export type PPEClassInfo = {
  key: string
  label_ar: string
  label_en: string
}

export type PPEClassesResponse = {
  items: PPEClassInfo[]
  default_enabled: string[]
  allowed: string[]
}

// ── Cameras ──────────────────────────────────────────────────────
export type CameraSourceType = "webcam" | "rtsp" | "file"

export type Camera = {
  id: number
  name: string
  source_type: CameraSourceType
  source_uri: string
  enabled_classes: string[]
  is_active: boolean
  created_at: string
  is_running: boolean
}

export type CameraCreatePayload = {
  name: string
  source_type: CameraSourceType
  source_uri: string
  enabled_classes: string[]
}

export type CameraUpdatePayload = {
  name?: string
  source_uri?: string
  enabled_classes?: string[] | null
}

// ── Violations ───────────────────────────────────────────────────
export type Violation = {
  id: number
  camera_id: number
  violation_type: string
  confidence: number
  timestamp: string
  frame_path?: string | null
  frame_url?: string | null
}

export type ViolationListResponse = {
  total: number
  page: number
  page_size: number
  items: Violation[]
}