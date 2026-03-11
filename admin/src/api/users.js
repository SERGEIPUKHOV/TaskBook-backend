import { request } from "./client";
export const usersApi = {
    list: (params) => {
        const qs = new URLSearchParams({ page: String(params.page), per_page: String(params.per_page) });
        if (params.search)
            qs.set("search", params.search);
        return request(`/admin/users?${qs}`);
    },
    setActive: (userId, is_active) => request(`/admin/users/${userId}/block`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
    }),
    setEmail: (userId, email) => request(`/admin/users/${userId}/email`, {
        method: "PATCH",
        body: JSON.stringify({ email }),
    }),
    resetPassword: (userId) => request(`/admin/users/${userId}/reset-password`, { method: "POST" }),
    impersonate: (userId) => request(`/admin/users/${userId}/impersonate`, { method: "POST" }),
};
