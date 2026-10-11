import axios from "axios"
import type {
  Camera,
  CameraCreatePayload,
  CameraUpdatePayload,
  HealthResponse,
  PPEClassInfo,
  Violation,
  ViolationListResponse,
} from "@/types"

export type PPEClassesResponse = {
  items: PPEClassInfo[]
  default_enabled: string[]
  allowed: string[]
}

// ✅ مفتاح الـ API بيتحط وقت الـ build من متغير بيئة (frontend/.env ->
// VITE_API_KEY) ولازم يطابق API_KEY في إعدادات الباك إند، وإلا كل
// عمليات الكتابة (إضافة/تعديل/حذف/تشغيل/إيقاف كاميرا، تأكيد مخالفة)
// هترجع 401 Unauthorized.
// ⚠️ القيمة دي بتبقى ظاهرة في الـ JS bundle النهائي (أي حد يفتح
// DevTools هيشوفها)، فده مناسب بس لأداة داخلية على شبكة مقفولة،
// مش لتطبيق متاح للعامة على الإنترنت بدون نظام مستخدمين حقيقي.
const API_KEY: string = import.meta.env.VITE_API_KEY ?? ""

export const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  },
  timeout: 30000,
})

// ── Health ───────────────────────────────────────────────────────
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health")
  return data
}

// ── PPE Classes (Meta) ───────────────────────────────────────────
export async function getPPEClassesMeta(): Promise<PPEClassesResponse> {
  const { data } = await api.get<PPEClassesResponse>("/meta/ppe-classes")
  return data
}

export async function getPPEClasses(): Promise<PPEClassInfo[]> {
  const meta = await getPPEClassesMeta()
  return meta.items
}

// ── Cameras ──────────────────────────────────────────────────────
export async function getCameras(): Promise<Camera[]> {
  const { data } = await api.get<Camera[]>("/cameras")
  return data
}

export async function getCamera(id: number): Promise<Camera> {
  const { data } = await api.get<Camera>(`/cameras/${id}`)
  return data
}

export async function createCamera(payload: CameraCreatePayload): Promise<Camera> {
  const { data } = await api.post<Camera>("/cameras", payload)
  return data
}

export async function updateCamera(id: number, payload: CameraUpdatePayload): Promise<Camera> {
  const { data } = await api.put<Camera>(`/cameras/${id}`, payload)
  return data
}

export async function deleteCamera(id: number): Promise<void> {
  await api.delete(`/cameras/${id}`)
}

export async function startCamera(id: number): Promise<void> {
  await api.post(`/cameras/${id}/start`)
}

export async function stopCamera(id: number): Promise<void> {
  await api.post(`/cameras/${id}/stop`)
}

// ── Violations ───────────────────────────────────────────────────
export async function getViolations(params?: {
  camera_id?: number
  violation_type?: string
  page?: number
  page_size?: number
  from?: string // ✅ ISO string
  to?: string   // ✅ ISO string
}): Promise<ViolationListResponse> {
  const { data } = await api.get<ViolationListResponse>("/violations", { params })
  return data
}

// ✅ جديد: يأشّر على المخالفة كـ "تمت معالجتها" (resolved_at في الباك إند)
export async function resolveViolation(id: number): Promise<Violation> {
  const { data } = await api.post<Violation>(`/violations/${id}/resolve`)
  return data
}

export function getViolationsExportUrl(cameraId?: number): string {
  const url = new URL("/api/v1/violations/export", window.location.origin)
  if (cameraId) url.searchParams.set("camera_id", String(cameraId))
  return url.toString()
}

// ── Streaming helpers ────────────────────────────────────────────
export function getMjpegStreamUrl(cameraId: number): string {
  return `/api/v1/stream/${cameraId}`
}

export function getWebSocketUrl(cameraId: number): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws"
  return `${proto}://${window.location.host}/api/v1/ws/${cameraId}`
}