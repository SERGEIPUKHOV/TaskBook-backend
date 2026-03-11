import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink } from "react-router-dom";
const links = [
    { to: "/dashboard", label: "Дашборд", icon: "▦" },
    { to: "/users", label: "Пользователи", icon: "👥" },
];
export function Sidebar() {
    return (_jsxs("aside", { className: "w-56 shrink-0 bg-white border-r border-border flex flex-col", children: [_jsxs("div", { className: "px-5 py-5 border-b border-border", children: [_jsx("span", { className: "font-semibold text-text-primary", children: "TaskBook" }), _jsx("span", { className: "ml-1 text-xs text-text-secondary font-medium", children: "Admin" })] }), _jsx("nav", { className: "flex-1 px-3 py-4 flex flex-col gap-1", children: links.map(({ to, label, icon }) => (_jsxs(NavLink, { to: to, className: ({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive
                        ? "bg-accent/10 text-accent"
                        : "text-text-secondary hover:bg-gray-50 hover:text-text-primary"}`, children: [_jsx("span", { children: icon }), label] }, to))) })] }));
}
