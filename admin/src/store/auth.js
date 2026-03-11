import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useContext, useState } from "react";
import { request } from "../api/client";
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
    const [token, setToken] = useState(() => localStorage.getItem("admin_token"));
    const login = async (email, password) => {
        const res = await request("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
        });
        if (!res.user.is_admin) {
            throw new Error("Доступ запрещён: нет прав администратора");
        }
        localStorage.setItem("admin_token", res.access_token);
        setToken(res.access_token);
    };
    const logout = () => {
        localStorage.removeItem("admin_token");
        setToken(null);
    };
    return _jsx(AuthContext.Provider, { value: { token, login, logout }, children: children });
}
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx)
        throw new Error("useAuth outside AuthProvider");
    return ctx;
}
