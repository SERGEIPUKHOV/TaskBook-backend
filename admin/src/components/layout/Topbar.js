import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useAuth } from "../../store/auth";
import { Button } from "../ui/Button";
export function Topbar({ title }) {
    const { logout } = useAuth();
    return (_jsxs("header", { className: "h-14 bg-white border-b border-border flex items-center justify-between px-6 shrink-0", children: [_jsx("h1", { className: "text-sm font-semibold text-text-primary", children: title }), _jsx(Button, { variant: "ghost", size: "sm", onClick: logout, children: "\u0412\u044B\u0439\u0442\u0438" })] }));
}
