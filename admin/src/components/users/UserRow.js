import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
function fmt(iso) {
    return new Date(iso).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "numeric" });
}
export function UserRow({ user, onBlock, onResetPassword, onSetEmail, onImpersonate }) {
    return (_jsxs("tr", { className: "border-b border-border last:border-0 hover:bg-surface transition-colors", children: [_jsx("td", { className: "py-3 px-4 text-sm text-text-primary font-medium", children: user.email }), _jsx("td", { className: "py-3 px-4", children: _jsx(Badge, { active: user.is_active }) }), _jsx("td", { className: "py-3 px-4 text-sm text-text-secondary tabular-nums", children: fmt(user.created_at) }), _jsx("td", { className: "py-3 px-4 text-sm text-text-secondary tabular-nums", children: user.tasks_count }), _jsx("td", { className: "py-3 px-4", children: _jsxs("div", { className: "flex items-center gap-1.5 justify-end flex-wrap", children: [_jsx(Button, { variant: "ghost", size: "sm", onClick: () => onSetEmail(user), children: "Email" }), _jsx(Button, { variant: "ghost", size: "sm", onClick: () => onResetPassword(user), children: "\u041F\u0430\u0440\u043E\u043B\u044C" }), _jsx(Button, { variant: "ghost", size: "sm", onClick: () => onImpersonate(user), children: "\u0412\u043E\u0439\u0442\u0438" }), _jsx(Button, { variant: user.is_active ? "danger" : "primary", size: "sm", onClick: () => onBlock(user), children: user.is_active ? "Заблокировать" : "Разблокировать" })] }) })] }));
}
