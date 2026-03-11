import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
const titles = {
    "/dashboard": "Обзор",
    "/users": "Пользователи",
};
export function AdminLayout() {
    const { pathname } = useLocation();
    const title = titles[pathname] ?? "Администрирование";
    return (_jsxs("div", { className: "flex h-screen bg-surface overflow-hidden", children: [_jsx(Sidebar, {}), _jsxs("div", { className: "flex flex-col flex-1 min-w-0", children: [_jsx(Topbar, { title: title }), _jsx("main", { className: "flex-1 overflow-y-auto p-6", children: _jsx(Outlet, {}) })] })] }));
}
