import { createContext, useContext, useState, type ReactNode } from "react"
import { request } from "../api/client"

interface AuthResponse {
  access_token: string
  user: { is_admin: boolean }
}

interface AuthCtx {
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("admin_token")
  )

  const login = async (email: string, password: string) => {
    const res = await request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
    if (!res.user.is_admin) {
      throw new Error("Доступ запрещён: нет прав администратора")
    }
    localStorage.setItem("admin_token", res.access_token)
    setToken(res.access_token)
  }

  const logout = () => {
    localStorage.removeItem("admin_token")
    setToken(null)
  }

  return <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth outside AuthProvider")
  return ctx
}
