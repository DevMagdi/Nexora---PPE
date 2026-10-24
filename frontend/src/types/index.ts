export type UserRole = "admin" | "supervisor" | "viewer"
export type RangeKey = "24h" | "7d"
export type TabKey = "overview" | "live" | "cameras" | "uploads" | "violations" | "sites" | "users"
export type SiteKind = "factory" | "construction" | "workshop" | "warehouse" | "industrial"
export type CameraSourceType = "rtsp" | "rtsps" | "http_mjpeg" | "hls" | "file" | "usb"
export type ConnectionStatus =
  "starting" | "running" | "retrying" | "stopped" | "completed" | "error"
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
  source_type: CameraSourceType
  source_uri: string
  site_id: number | null
  enabled_classes: RuleKey[]
  is_active: boolean
  created_at: string
  is_running: boolean
  connection_status: ConnectionStatus
  last_error: string | null
  device_index: number | null
  port: number | null
  auth_mode: "basic" | "digest"
  onvif_device_uri: string | null
}
export interface CameraSourceFields {
  source_uri?: string
  device_index?: number
  port?: number
  source_username?: string
  source_password?: string
  clear_credentials?: boolean
  auth_mode?: "basic" | "digest"
  onvif_device_uri?: string | null
}
export interface CameraCreatePayload extends CameraSourceFields {
  name: string
  source_type: CameraSourceType
  site_id: number | null
  enabled_classes: RuleKey[]
}
export interface CameraUpdatePayload extends CameraSourceFields {
  name: string
  source_type?: CameraSourceType
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
  negative_confidence?: number
  effective_negative_confidence?: number
  platform_name?: "Mantik PPE"
  capabilities_known?: boolean
  supported_negative_rules?: RuleKey[] | null
  max_upload_mb: number
  max_video_seconds: number
  supported_source_types: CameraSourceType[]
  recommended_source_type: "rtsp"
  rtsp_sources_enabled: boolean
  http_sources_enabled: boolean
  file_sources_enabled: boolean
  usb_sources_enabled: boolean
  usb_device_indices: number[]
  onvif_mode: "metadata_only"
  rules: {
    key: RuleKey
    label_ar: string
    label_en: string
    positive_supported?: boolean | null
    negative_supported?: boolean | null
  }[]
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
  detections: {
    class_name: string
    confidence: number
    box: number[]
    person_index?: number | null
  }[]
  preview: string
  width: number
  height: number
}
