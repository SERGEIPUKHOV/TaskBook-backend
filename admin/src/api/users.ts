import { request } from "./client"

export interface AdminUser {
  id: string
  email: string
  is_active: boolean
  is_admin: boolean
  created_at: string
  tasks_count: number
}

export interface UsersPage {
  items: AdminUser[]
  total: number
  page: number
  per_page: number
}

export interface ResetPasswordResult {
  temp_password: string
}

export const usersApi = {
  list: (params: { page: number; per_page: number; search?: string }) => {
    const qs = new URLSearchParams({ page: String(params.page), per_page: String(params.per_page) })
    if (params.search) qs.set("search", params.search)
    return request<UsersPage>(`/admin/users?${qs}`)
  },
  setActive: (userId: string, is_active: boolean) =>
    request<AdminUser>(`/admin/users/${userId}/block`, {
      method: "PATCH",
      body: JSON.stringify({ is_active }),
    }),
  setEmail: (userId: string, email: string) =>
    request<AdminUser>(`/admin/users/${userId}/email`, {
      method: "PATCH",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (userId: string) =>
    request<ResetPasswordResult>(`/admin/users/${userId}/reset-password`, { method: "POST" }),
  impersonate: (userId: string) =>
    request<{ code: string }>(`/admin/users/${userId}/impersonate`, { method: "POST" }),
}
