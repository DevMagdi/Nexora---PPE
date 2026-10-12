export type CameraSourceType = "webcam" | "rtsp" | "file"
export type CameraProfile = "construction" | "medical"
export type UserSector = "construction" | "medical" | "both"

export interface Camera {
  id: number
  name: string
  source_type: CameraSourceType
  source_uri: string
  profile: CameraProfile
  enabled_classes: string[]
  is_active: boolean
  created_at: string
  is_running: boolean
}

export interface CameraCreatePayload {
  name: string
  source_type: CameraSourceType
  source_uri: string
  profile?: CameraProfile
  enabled_classes?: string[]
}

export interface CameraUpdatePayload {
  name?: string
  source_uri?: string
  enabled_classes?: string[]
}

export interface Violation {
  id: number
  camera_id: number
  violation_type: string
  confidence: number
  timestamp: string
  resolved_at: string | null
  is_resolved: boolean
  frame_path: string | null
  frame_url: string | null
}

export interface ViolationListResponse {
  total: number
  page: number
  page_size: number
  items: Violation[]
}

export interface HealthResponse {
  status: "ok" | string
}

export interface PPEClassInfo {
  key: string
  label_ar: string
  label_en: string
}

export interface PPEClassesResponse {
  profile: CameraProfile
  items: PPEClassInfo[]
  default_enabled: string[]
  allowed: string[]
}

export interface LoginResponse {
  authenticated: boolean
  must_change_password: boolean
}

export type UserRole = "admin" | "operator" | "viewer"

export interface MeResponse {
  id: number
  username: string
  sector: UserSector
  role: UserRole
  must_change_password: boolean
}

/** الشكل الفعلي لرسالة الـ WS من CameraManager._compute_counts */
export interface LiveCountsRaw {
  ping?: boolean
  hardhat?: number
  vest?: number
  person?: number
  no_mask?: number
  no_gloves?: number
  no_goggles?: number
  no_cap?: number
  skin_hits?: number
  total?: number
  // مفاتيح قديمة لو في نسخة باك أقدم
  hardhat_count?: number
  vest_count?: number
  person_count?: number
  total_detections?: number
}

/* ─── UI & Dashboard Types ─── */

export type RangeKey = "24h" | "7d"
export type TabKey = "overview" | "live" | "cameras" | "violations"
export type ToneKey = "primary" | "info" | "warning" | "destructive" | "success"
export type LiveStatus = "idle" | "connecting" | "open" | "reconnecting"
export type ViolationStatusFilter = "all" | "open" | "resolved"

export interface ToastState {
  id: number
  tone: "success" | "error"
  text: string
}

export interface LiveCounts {
  hardhat?: number
  vest?: number
  person?: number
  no_mask?: number
  no_gloves?: number
  no_goggles?: number
  no_cap?: number
  /** كشوف أكّدها/ولّدها فلتر الجلد (distanceTransform / جسر العينين) */
  skin_hits?: number
  total?: number
}

export interface LiveMetricItem {
  value: number | undefined
  label: string
}
