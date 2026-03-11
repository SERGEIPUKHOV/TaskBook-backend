import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { UserRow } from "./UserRow";
export function UserTable({ users, onBlock, onResetPassword, onSetEmail, onImpersonate, loading }) {
    if (loading)
        return (_jsx("div", { className: "flex justify-center py-12", children: _jsxs("svg", { className: "animate-spin h-6 w-6 text-accent", viewBox: "0 0 24 24", fill: "none", children: [_jsx("circle", { className: "opacity-25", cx: "12", cy: "12", r: "10", stroke: "currentColor", strokeWidth: "4" }), _jsx("path", { className: "opacity-75", fill: "currentColor", d: "M4 12a8 8 0 018-8v8H4z" })] }) }));
    if (users.length === 0)
        return (_jsx("p", { className: "text-center py-12 text-sm text-text-secondary", children: "\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438 \u043E\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u044E\u0442" }));
    return (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "min-w-full", children: [_jsx("thead", { children: _jsx("tr", { className: "border-b border-border bg-surface", children: ["Email", "Статус", "Дата регистрации", "Задач", "Действие"].map((h) => (_jsx("th", { className: "py-3 px-4 text-left text-xs font-semibold text-text-secondary uppercase tracking-wide", children: h }, h))) }) }), _jsx("tbody", { children: users.map((u) => (_jsx(UserRow, { user: u, onBlock: onBlock, onResetPassword: onResetPassword, onSetEmail: onSetEmail, onImpersonate: onImpersonate }, u.id))) })] }) }));
}
