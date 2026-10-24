export type UserRole = "admin" | "supervisor" | "viewer"
export type RangeKey = "24h" | "7d"
export type TabKey = "overview" | "live" | "cameras" | "uploads" | "violations" | "sites" | "users"
export type SiteKind = "factory" | "construction" | "workshop" | "warehouse" | "industrial"
export type RuleKey = "helmet" | "vest" | "gloves" | "boots" | "goggles"

export interface MeResponse {
  id: number
  username: string
  role: UserRole
  must_change_password: boolean
}
export interface LoginResponse {
  authenticated: boolean
  must_change_password: boolean
}
export interface Site {
  id: number
  name: string
  kind: SiteKind
  location: string
  created_at: string
}
export interface SitePayload {
  name: string
  kind: SiteKind
  location: string
}
export interface Camera {
  id: number
  name: string
  source_type: "rtsp" | "file"
  source_uri: string
  site_id: number | null
  enabled_classes: RuleKey[]
  is_active: boolean
  created_at: string
  is_running: boolean
}
export interface CameraCreatePayload {
  name: string
  source_type: "rtsp" | "file"
  source_uri: string
  site_id: number | null
  enabled_classes: RuleKey[]
}
export interface CameraUpdatePayload {
  name: string
  source_uri?: string
  site_id: number | null
  enabled_classes: RuleKey[]
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
export interface ViolationFilters {
  camera_id?: number
  site_id?: number
  violation_type?: string
  status?: "all" | "open" | "resolved"
  from?: string
  to?: string
  page?: number
  page_size?: number
}
export interface LiveCounts {
  person: number
  hardhat: number
  no_hardhat: number
  vest: number
  no_vest: number
  gloves: number
  no_gloves: number
  boots: number
  no_boot: number
  goggles: number
  no_goggles: number
  total: number
}
export interface SystemMeta {
  scope: "industrial"
  model: "ppe_unified_best.pt"
  confidence: number
  max_upload_mb: number
  max_video_seconds: number
  rules: { key: RuleKey; label_ar: string; label_en: string }[]
}
export interface DashboardData {
  range: RangeKey
  from: string
  to: string
  total_events: number
  open_events: number
  resolved_events: number
  total_cameras: number
  running_cameras: number
  sites: number
  live_people: number
  series: { timestamp: string; count: number }[]
  breakdown: { type: string; count: number }[]
}
export interface UserAccount extends MeResponse {
  is_active: boolean
  created_at: string
}
export interface IssuedAccount extends UserAccount {
  initial_password: string
}
export interface ImageResult {
  detections: { class_name: string; confidence: number; box: number[] }[]
  preview: string
  width: number
  height: number
}
