import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
export function BlockUserModal({ user, onClose, onConfirm, loading }) {
    if (!user)
        return null;
    const isBlocking = user.is_active;
    return (_jsx(Modal, { open: !!user, title: isBlocking ? "Заблокировать пользователя" : "Разблокировать пользователя", onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx(Button, { variant: "ghost", size: "sm", onClick: onClose, disabled: loading, children: "\u041E\u0442\u043C\u0435\u043D\u0430" }), _jsx(Button, { variant: isBlocking ? "danger" : "primary", size: "sm", loading: loading, onClick: () => onConfirm(user), children: isBlocking ? "Заблокировать" : "Разблокировать" })] }), children: _jsxs("p", { className: "text-sm text-text-secondary", children: ["\u0412\u044B \u0443\u0432\u0435\u0440\u0435\u043D\u044B, \u0447\u0442\u043E \u0445\u043E\u0442\u0438\u0442\u0435 ", isBlocking ? "заблокировать" : "разблокировать", " \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u044F", " ", _jsx("span", { className: "font-medium text-text-primary", children: user.email }), "?"] }) }));
}
