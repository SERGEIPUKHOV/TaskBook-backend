import { request } from "./client"

export interface PlatformStats {
  total_users: number
  active_7d: number
  total_tasks: number
  total_habits: number
}

export const statsApi = {
  get: () => request<PlatformStats>("/admin/stats"),
}
