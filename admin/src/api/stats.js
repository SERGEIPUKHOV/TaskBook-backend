import { request } from "./client";
export const statsApi = {
    get: () => request("/admin/stats"),
};
