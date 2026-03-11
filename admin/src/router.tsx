import { createBrowserRouter, Navigate } from "react-router-dom"
import { LoginPage } from "./pages/LoginPage"
import { DashboardPage } from "./pages/DashboardPage"
import { UsersPage } from "./pages/UsersPage"
import { AdminLayout } from "./components/layout/AdminLayout"
import { useAuth } from "./store/auth"
import type { ReactNode } from "react"

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    path: "/",
    element: <ProtectedRoute><AdminLayout /></ProtectedRoute>,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "users", element: <UsersPage /> },
    ],
  },
])
