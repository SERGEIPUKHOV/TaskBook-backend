import { NavLink } from "react-router-dom"

const links = [
  { to: "/dashboard", label: "Дашборд", icon: "▦" },
  { to: "/users",     label: "Пользователи", icon: "👥" },
]

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 bg-white border-r border-border flex flex-col">
      <div className="px-5 py-5 border-b border-border">
        <span className="font-semibold text-text-primary">TaskBook</span>
        <span className="ml-1 text-xs text-text-secondary font-medium">Admin</span>
      </div>
      <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
        {links.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-text-secondary hover:bg-gray-50 hover:text-text-primary"
              }`
            }
          >
            <span>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
