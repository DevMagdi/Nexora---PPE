import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  getHealth,
  getPPEClasses,
  getPPEClassesMeta,
  getCameras,
  getCamera,
  createCamera,
  updateCamera,
  deleteCamera,
  startCamera,
  stopCamera,
  getViolations,
} from "@/lib/api"
import type { CameraCreatePayload, CameraUpdatePayload } from "@/types"

// ── Query Keys ───────────────────────────────────────────────────
export const queryKeys = {
  health: ["health"] as const,

  // PPE
  ppeClassesMeta: ["ppe-classes-meta"] as const,
  ppeClasses: ["ppe-classes"] as const,

  // Cameras
  cameras: ["cameras"] as const,
  camera: (id: number) => ["cameras", id] as const,

  // Violations
  violations: (params?: Record<string, unknown>) => ["violations", params ?? {}] as const,
}

// ── Health ───────────────────────────────────────────────────────
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: getHealth,
    refetchInterval: 5000,
    retry: false,
  })
}

// ── PPE Classes ──────────────────────────────────────────────────
export function usePPEClassesMeta() {
  return useQuery({
    queryKey: queryKeys.ppeClassesMeta,
    queryFn: getPPEClassesMeta,
    staleTime: Infinity,
  })
}

// بيرجع items بس (array) — ده اللي غالبًا محتاجه الـ UI
export function usePPEClasses() {
  return useQuery({
    queryKey: queryKeys.ppeClasses,
    queryFn: getPPEClasses,
    staleTime: Infinity,
  })
}

// ── Cameras ──────────────────────────────────────────────────────
export function useCameras() {
  return useQuery({
    queryKey: queryKeys.cameras,
    queryFn: getCameras,
    refetchInterval: 5000,
  })
}

export function useCamera(id: number | null) {
  return useQuery({
    queryKey: queryKeys.camera(id ?? -1),
    queryFn: () => getCamera(id as number),
    enabled: id !== null,
  })
}

export function useCreateCamera() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CameraCreatePayload) => createCamera(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras })
    },
  })
}

export function useUpdateCamera() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CameraUpdatePayload }) =>
      updateCamera(id, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras })
      queryClient.invalidateQueries({ queryKey: queryKeys.camera(variables.id) })
    },
  })
}

export function useDeleteCamera() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteCamera(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras })
    },
  })
}

export function useStartCamera() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => startCamera(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras })
    },
  })
}

export function useStopCamera() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => stopCamera(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras })
    },
  })
}

// ── Violations ───────────────────────────────────────────────────
export function useViolations(params?: {
  camera_id?: number
  violation_type?: string
  page?: number
  page_size?: number
}) {
  return useQuery({
    queryKey: queryKeys.violations(params as any),
    queryFn: () => getViolations(params),
    refetchInterval: 5000,
  })
}