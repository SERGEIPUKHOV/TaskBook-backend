import { Outlet, useLocation } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { Topbar } from "./Topbar"

const titles: Record<string, string> = {
  "/dashboard": "Обзор",
  "/users": "Пользователи",
}

export function AdminLayout() {
  const { pathname } = useLocation()
  const title = titles[pathname] ?? "Администрирование"
  return (
    <div className="flex h-screen bg-surface overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <Topbar title={title} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
