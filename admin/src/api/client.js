const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";
function getToken() {
    return localStorage.getItem("admin_token");
}
export async function request(path, init) {
    const token = getToken();
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...init?.headers,
        },
    });
    if (res.status === 401) {
        localStorage.removeItem("admin_token");
        window.location.href = "/login";
        throw new Error("Unauthorized");
    }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Не удалось выполнить запрос");
    }
    if (res.status === 204)
        return undefined;
    const json = await res.json();
    return json.data;
}
