import axios from "axios"
import type {
  Camera,
  CameraCreatePayload,
  CameraUpdatePayload,
  DashboardData,
  ImageResult,
  IssuedAccount,
  LoginResponse,
  MeResponse,
  RangeKey,
  Site,
  SitePayload,
  SystemMeta,
  UserAccount,
  UserRole,
  Violation,
  ViolationFilters,
  ViolationListResponse,
} from "@/types"

export const api = axios.create({ baseURL: "/api/v1", timeout: 30_000, withCredentials: true })

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && !String(error?.config?.url).startsWith("/auth/"))
      window.location.assign("/")
    return Promise.reject(error)
  },
)

export async function me(): Promise<MeResponse> {
  return (await api.get("/auth/me")).data
}
export async function login(username: string, password: string): Promise<LoginResponse> {
  return (await api.post("/auth/login", new URLSearchParams({ username, password }))).data
}
export async function logout(): Promise<void> {
  await api.post("/auth/logout")
}
export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<LoginResponse> {
  return (
    await api.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    })
  ).data
}
export async function refreshMediaSession(): Promise<void> {
  await api.post("/auth/media-token")
}
export async function getHealth(): Promise<{ status: string }> {
  return (await api.get("/health")).data
}
export async function getSystemMeta(): Promise<SystemMeta> {
  return (await api.get("/meta/system")).data
}
export async function getCameras(): Promise<Camera[]> {
  return (await api.get("/cameras")).data
}
export async function createCamera(payload: CameraCreatePayload): Promise<Camera> {
  return (await api.post("/cameras", payload)).data
}
export async function updateCamera(id: number, payload: CameraUpdatePayload): Promise<Camera> {
  return (await api.put(`/cameras/${id}`, payload)).data
}
export async function deleteCamera(id: number): Promise<void> {
  await api.delete(`/cameras/${id}`)
}
export async function startCamera(id: number): Promise<void> {
  await refreshMediaSession()
  await api.post(`/cameras/${id}/start`)
}
export async function stopCamera(id: number): Promise<void> {
  await api.post(`/cameras/${id}/stop`)
}
export async function getSites(): Promise<Site[]> {
  return (await api.get("/sites")).data
}
export async function createSite(payload: SitePayload): Promise<Site> {
  return (await api.post("/sites", payload)).data
}
export async function updateSite(id: number, payload: SitePayload): Promise<Site> {
  return (await api.put(`/sites/${id}`, payload)).data
}
export async function deleteSite(id: number): Promise<void> {
  await api.delete(`/sites/${id}`)
}
export async function getDashboard(range: RangeKey, siteId?: number): Promise<DashboardData> {
  return (await api.get("/dashboard", { params: { range, site_id: siteId } })).data
}
export async function getViolations(params: ViolationFilters): Promise<ViolationListResponse> {
  return (await api.get("/violations", { params })).data
}
export async function resolveViolation(id: number): Promise<Violation> {
  return (await api.post(`/violations/${id}/resolve`)).data
}
export async function downloadViolationsCsv(params: ViolationFilters): Promise<void> {
  const { data } = await api.get<Blob>("/violations/export", { params, responseType: "blob" })
  const url = URL.createObjectURL(new Blob(["\ufeff", data], { type: "text/csv;charset=utf-8" }))
  const link = document.createElement("a")
  link.href = url
  link.download = "mantik-industrial-events.csv"
  link.click()
  URL.revokeObjectURL(url)
}
export async function getUsers(): Promise<UserAccount[]> {
  return (await api.get("/auth/users")).data
}
export async function createUser(
  username: string,
  role: Exclude<UserRole, "admin">,
): Promise<IssuedAccount> {
  return (await api.post("/auth/users", { username, role })).data
}
export async function updateUser(
  id: number,
  payload: { role?: Exclude<UserRole, "admin">; is_active?: boolean },
): Promise<UserAccount> {
  return (await api.patch(`/auth/users/${id}`, payload)).data
}
export async function resetUserPassword(id: number): Promise<IssuedAccount> {
  return (await api.post(`/auth/users/${id}/reset-password`)).data
}
export async function inferImage(body: FormData): Promise<ImageResult> {
  return (await api.post("/inference/image", body, { timeout: 120_000 })).data
}
export async function uploadVideo(body: FormData): Promise<Camera> {
  return (await api.post("/inference/video", body, { timeout: 180_000 })).data
}
export function getMjpegStreamUrl(id: number): string {
  return `/api/v1/stream/${id}`
}
export function getWebSocketUrl(id: number): string {
  return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api/v1/ws/${id}`
}
export function resolveFrameUrl(value: string | null): string | null {
  // Evidence is served only by this application's authenticated media route.
  return value?.startsWith("/frames/") && !value.includes("..") ? value : null
}
