import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { CameraCreatePayload, CameraUpdatePayload } from "@/types"
import {
  createCamera,
  deleteCamera,
  downloadViolationsCsv,
  getCameras,
  getHealth,
  getPPEClassesMeta,
  getViolations,
  login,
  me,
  resolveViolation,
  setToken,
  startCamera,
  stopCamera,
  updateCamera,
} from "@/lib/api"

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: me,
    retry: false,
    staleTime: 30_000,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { username: string; password: string }) => {
      const res = await login(vars.username, vars.password)
      setToken(res.access_token)
      return res
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me"] })
      await qc.invalidateQueries({ queryKey: ["cameras"] })
      await qc.invalidateQueries({ queryKey: ["ppe-meta"] })
      await qc.invalidateQueries({ queryKey: ["health"] })
    },
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10_000,
  })
}

export function usePPEClassesMeta(profile?: "construction" | "medical", enabled = true) {
  return useQuery({
    queryKey: ["ppe-meta", profile ?? "auto"],
    queryFn: () => getPPEClassesMeta(profile),
    staleTime: 60_000,
    enabled,
  })
}

export function useCameras() {
  return useQuery({
    queryKey: ["cameras"],
    queryFn: getCameras,
    refetchInterval: 5_000,
  })
}

export function useCreateCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CameraCreatePayload) => createCamera(payload),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["cameras"] })
    },
  })
}

export function useUpdateCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; payload: CameraUpdatePayload }) => updateCamera(vars.id, vars.payload),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["cameras"] })
    },
  })
}

export function useDeleteCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteCamera(id),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["cameras"] })
    },
  })
}

export function useStartCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await startCamera(id)
      return id
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["cameras"] })
    },
  })
}

export function useStopCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await stopCamera(id)
      return id
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["cameras"] })
    },
  })
}

export function useViolations(params?: Parameters<typeof getViolations>[0]) {
  return useQuery({
    queryKey: ["violations", params ?? {}],
    queryFn: () => getViolations(params),
    refetchInterval: 10_000,
  })
}

export function useResolveViolation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => resolveViolation(id),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["violations"] })
    },
  })
}

export function useExportViolations() {
  return useMutation({
    mutationFn: (params?: Parameters<typeof downloadViolationsCsv>[0]) => downloadViolationsCsv(params),
  })
}