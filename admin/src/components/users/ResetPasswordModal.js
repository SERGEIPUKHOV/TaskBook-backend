import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
export function ResetPasswordModal({ user, onClose, onConfirm }) {
    const [loading, setLoading] = useState(false);
    const [tempPassword, setTempPassword] = useState(null);
    const handleConfirm = async () => {
        if (!user)
            return;
        setLoading(true);
        try {
            const pw = await onConfirm(user);
            setTempPassword(pw);
        }
        finally {
            setLoading(false);
        }
    };
    const handleClose = () => { setTempPassword(null); onClose(); };
    if (!user)
        return null;
    return (_jsx(Modal, { open: !!user, title: "\u0421\u0431\u0440\u043E\u0441 \u043F\u0430\u0440\u043E\u043B\u044F", onClose: handleClose, footer: tempPassword ? (_jsx(Button, { variant: "ghost", size: "sm", onClick: handleClose, children: "\u0417\u0430\u043A\u0440\u044B\u0442\u044C" })) : (_jsxs(_Fragment, { children: [_jsx(Button, { variant: "ghost", size: "sm", onClick: handleClose, disabled: loading, children: "\u041E\u0442\u043C\u0435\u043D\u0430" }), _jsx(Button, { variant: "danger", size: "sm", loading: loading, onClick: handleConfirm, children: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u043F\u0430\u0440\u043E\u043B\u044C" })] })), children: tempPassword ? (_jsxs("div", { className: "flex flex-col gap-3", children: [_jsxs("p", { className: "text-sm text-text-secondary", children: ["\u0412\u0440\u0435\u043C\u0435\u043D\u043D\u044B\u0439 \u043F\u0430\u0440\u043E\u043B\u044C \u0434\u043B\u044F ", _jsx("span", { className: "font-medium text-text-primary", children: user.email }), ":"] }), _jsx("code", { className: "block bg-surface border border-border rounded-lg px-4 py-3 text-sm font-mono text-text-primary select-all", children: tempPassword }), _jsx("p", { className: "text-xs text-text-secondary", children: "\u0421\u043A\u043E\u043F\u0438\u0440\u0443\u0439\u0442\u0435 \u0438 \u043F\u0435\u0440\u0435\u0434\u0430\u0439\u0442\u0435 \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u044E. \u041E\u043D \u0441\u043C\u043E\u0436\u0435\u0442 \u0432\u043E\u0439\u0442\u0438 \u0438 \u0441\u043C\u0435\u043D\u0438\u0442\u044C \u043F\u0430\u0440\u043E\u043B\u044C." })] })) : (_jsxs("p", { className: "text-sm text-text-secondary", children: ["\u0421\u0433\u0435\u043D\u0435\u0440\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u0432\u0440\u0435\u043C\u0435\u043D\u043D\u044B\u0439 \u043F\u0430\u0440\u043E\u043B\u044C \u0434\u043B\u044F", " ", _jsx("span", { className: "font-medium text-text-primary", children: user.email }), "? \u0422\u0435\u043A\u0443\u0449\u0438\u0439 \u043F\u0430\u0440\u043E\u043B\u044C \u0431\u0443\u0434\u0435\u0442 \u0441\u0431\u0440\u043E\u0448\u0435\u043D."] })) }));
}
