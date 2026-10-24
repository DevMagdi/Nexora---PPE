import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getCameras,
  getDashboard,
  getHealth,
  getSites,
  getSystemMeta,
  getUsers,
  getViolations,
  me,
} from "@/lib/api"
import type { RangeKey, ViolationFilters } from "@/types"

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: me, retry: false, staleTime: 30_000 })
}
export function useCameras() {
  return useQuery({ queryKey: ["cameras"], queryFn: getCameras, refetchInterval: 5_000 })
}
export function useSites() {
  return useQuery({ queryKey: ["sites"], queryFn: getSites })
}
export function useSystem() {
  return useQuery({ queryKey: ["system"], queryFn: getSystemMeta, staleTime: 60_000 })
}
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: false,
  })
}
export function useDashboard(range: RangeKey, siteId?: number) {
  return useQuery({
    queryKey: ["dashboard", range, siteId],
    queryFn: () => getDashboard(range, siteId),
    refetchInterval: 10_000,
  })
}
export function useViolations(params: ViolationFilters) {
  return useQuery({
    queryKey: ["violations", params],
    queryFn: () => getViolations(params),
    refetchInterval: 10_000,
  })
}
export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: getUsers })
}
export function useRefresh() {
  const client = useQueryClient()
  return async () => {
    await Promise.all(
      ["cameras", "sites", "dashboard", "violations", "users"].map((key) =>
        client.invalidateQueries({ queryKey: [key] }),
      ),
    )
  }
}
