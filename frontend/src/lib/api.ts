import axios from "axios"
import type {
  Camera,
  CameraCreatePayload,
  CameraUpdatePayload,
  HealthResponse,
  PPEClassesResponse,
  PPEClassInfo,
  Violation,
  ViolationListResponse,
  LoginResponse,
  MeResponse,
} from "@/types"

export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
  withCredentials: true,
})

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401) {
      const url = String(error?.config?.url ?? "")
      if (
        !url.includes("/auth/login")
        && !url.includes("/auth/logout")
        && !url.includes("/auth/me")
      ) {
        window.location.assign("/")
      }
    }
    return Promise.reject(error)
  },
)

export async function login(username: string, password: string): Promise<LoginResponse> {
  const body = new URLSearchParams({ username, password })
  const { data } = await api.post<LoginResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  })
  return data
}

export async function refreshMediaSession(): Promise<void> {
  await api.post("/auth/media-token")
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return data
}

export async function logout(): Promise<void> {
  try {
    await api.post("/auth/logout")
  } finally {
    window.location.assign("/")
  }
}

export async function me(): Promise<MeResponse> {
  const { data } = await api.get<MeResponse>("/auth/me")
  return data
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health")
  return data
}

export async function getPPEClassesMeta(profile?: "construction" | "medical"): Promise<PPEClassesResponse> {
  const { data } = await api.get<PPEClassesResponse>("/meta/ppe-classes", {
    params: profile ? { profile } : undefined,
  })
  return data
}

export async function getPPEClasses(profile?: "construction" | "medical"): Promise<PPEClassInfo[]> {
  const meta = await getPPEClassesMeta(profile)
  return meta.items
}

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

export async function getViolations(params?: {
  camera_id?: number
  violation_type?: string
  page?: number
  page_size?: number
  from?: string
  to?: string
}): Promise<ViolationListResponse> {
  const { data } = await api.get<ViolationListResponse>("/violations", { params })
  return data
}

export async function resolveViolation(id: number): Promise<Violation> {
  const { data } = await api.post<Violation>(`/violations/${id}/resolve`)
  return data
}

/** تحميل CSV بنفس التوكن (الـ endpoint محمي بـ Bearer) */
export async function downloadViolationsCsv(params?: {
  camera_id?: number
  violation_type?: string
  from?: string
  to?: string
}): Promise<void> {
  const { data } = await api.get<Blob>("/violations/export", {
    params,
    responseType: "blob",
  })
  const blob = new Blob([data], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "violations.csv"
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** Media endpoints authenticate with a short-lived HttpOnly cookie, never a URL token. */
export function resolveFrameUrl(frameUrl?: string | null): string | null {
  if (!frameUrl) return null
  if (/^https?:\/\//i.test(frameUrl)) return frameUrl
  return frameUrl.startsWith("/") ? frameUrl : `/${frameUrl}`
}

export function getMjpegStreamUrl(cameraId: number): string {
  return `/api/v1/stream/${cameraId}`
}

export function getWebSocketUrl(cameraId: number): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws"
  return `${proto}://${window.location.host}/api/v1/ws/${cameraId}`
}
