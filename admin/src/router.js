import { Fragment as _Fragment, jsx as _jsx } from "react/jsx-runtime";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { UsersPage } from "./pages/UsersPage";
import { AdminLayout } from "./components/layout/AdminLayout";
import { useAuth } from "./store/auth";
function ProtectedRoute({ children }) {
    const { token } = useAuth();
    return token ? _jsx(_Fragment, { children: children }) : _jsx(Navigate, { to: "/login", replace: true });
}
export const router = createBrowserRouter([
    { path: "/login", element: _jsx(LoginPage, {}) },
    {
        path: "/",
        element: _jsx(ProtectedRoute, { children: _jsx(AdminLayout, {}) }),
        children: [
            { index: true, element: _jsx(Navigate, { to: "/dashboard", replace: true }) },
            { path: "dashboard", element: _jsx(DashboardPage, {}) },
            { path: "users", element: _jsx(UsersPage, {}) },
        ],
    },
]);
