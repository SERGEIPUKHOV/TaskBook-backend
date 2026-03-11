import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from "react";
import { usersApi } from "../api/users";
import { UserTable } from "../components/users/UserTable";
import { UserSearchBar } from "../components/users/UserSearchBar";
import { BlockUserModal } from "../components/users/BlockUserModal";
import { ResetPasswordModal } from "../components/users/ResetPasswordModal";
import { SetEmailModal } from "../components/users/SetEmailModal";
import { Pagination } from "../components/ui/Pagination";
import { Toast, useToast } from "../components/ui/Toast";
const FRONTEND_URL = import.meta.env.VITE_FRONTEND_URL ?? "http://localhost:3001";
export function UsersPage() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [blockTarget, setBlockTarget] = useState(null);
    const [blockLoading, setBlockLoading] = useState(false);
    const [resetTarget, setResetTarget] = useState(null);
    const [emailTarget, setEmailTarget] = useState(null);
    const { toast, show: showToast, hide: hideToast } = useToast();
    const load = useCallback(() => {
        setLoading(true);
        usersApi.list({ page, per_page: 20, search: search || undefined })
            .then(setData)
            .catch(() => showToast("Ошибка загрузки", "error"))
            .finally(() => setLoading(false));
    }, [page, search, showToast]);
    useEffect(() => { load(); }, [load]);
    const handleSearch = (v) => { setSearch(v); setPage(1); };
    const handleBlock = async (user) => {
        setBlockLoading(true);
        try {
            const updated = await usersApi.setActive(user.id, !user.is_active);
            setData((prev) => prev ? { ...prev, items: prev.items.map((u) => u.id === updated.id ? updated : u) } : prev);
            showToast(updated.is_active ? "Пользователь разблокирован" : "Пользователь заблокирован");
            setBlockTarget(null);
        }
        catch (e) {
            showToast(e instanceof Error ? e.message : "Ошибка", "error");
        }
        finally {
            setBlockLoading(false);
        }
    };
    const handleResetPassword = async (user) => {
        const result = await usersApi.resetPassword(user.id);
        showToast("Пароль сброшен");
        return result.temp_password;
    };
    const handleSetEmail = async (user, email) => {
        const updated = await usersApi.setEmail(user.id, email);
        setData((prev) => prev ? { ...prev, items: prev.items.map((u) => u.id === updated.id ? updated : u) } : prev);
        showToast("Email обновлён");
    };
    const handleImpersonate = async (user) => {
        try {
            const { code } = await usersApi.impersonate(user.id);
            window.open(`${FRONTEND_URL}/auth/impersonate?code=${code}`, "_blank");
        }
        catch (e) {
            showToast(e instanceof Error ? e.message : "Ошибка", "error");
        }
    };
    return (_jsxs("div", { className: "max-w-5xl", children: [_jsxs("div", { className: "flex items-center justify-between mb-5", children: [_jsx("h2", { className: "text-base font-semibold text-text-primary", children: "\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438" }), _jsxs("span", { className: "text-sm text-text-secondary tabular-nums", children: [data?.total ?? "—", " \u0432\u0441\u0435\u0433\u043E"] })] }), _jsxs("div", { className: "bg-white rounded-2xl border border-border overflow-hidden shadow-sm", children: [_jsx("div", { className: "px-4 py-3 border-b border-border", children: _jsx(UserSearchBar, { value: search, onChange: handleSearch }) }), _jsx(UserTable, { users: data?.items ?? [], loading: loading, onBlock: setBlockTarget, onResetPassword: setResetTarget, onSetEmail: setEmailTarget, onImpersonate: handleImpersonate }), _jsx("div", { className: "px-4 border-t border-border", children: _jsx(Pagination, { page: page, total: data?.total ?? 0, perPage: 20, onChange: setPage }) })] }), _jsx(BlockUserModal, { user: blockTarget, onClose: () => setBlockTarget(null), onConfirm: handleBlock, loading: blockLoading }), _jsx(ResetPasswordModal, { user: resetTarget, onClose: () => setResetTarget(null), onConfirm: handleResetPassword }), _jsx(SetEmailModal, { user: emailTarget, onClose: () => setEmailTarget(null), onConfirm: handleSetEmail }), toast && _jsx(Toast, { message: toast.message, type: toast.type, onClose: hideToast })] }));
}
