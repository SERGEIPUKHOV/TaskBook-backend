import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
export function SetEmailModal({ user, onClose, onConfirm }) {
    const [email, setEmail] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const handleClose = () => { setEmail(""); setError(""); onClose(); };
    const handleConfirm = async () => {
        if (!user)
            return;
        if (!email.includes("@")) {
            setError("Введите корректный email");
            return;
        }
        setLoading(true);
        try {
            await onConfirm(user, email);
            handleClose();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : "Ошибка");
        }
        finally {
            setLoading(false);
        }
    };
    if (!user)
        return null;
    return (_jsx(Modal, { open: !!user, title: "\u0418\u0437\u043C\u0435\u043D\u0438\u0442\u044C email", onClose: handleClose, footer: _jsxs(_Fragment, { children: [_jsx(Button, { variant: "ghost", size: "sm", onClick: handleClose, disabled: loading, children: "\u041E\u0442\u043C\u0435\u043D\u0430" }), _jsx(Button, { size: "sm", loading: loading, onClick: handleConfirm, children: "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C" })] }), children: _jsxs("div", { className: "flex flex-col gap-4", children: [_jsxs("p", { className: "text-sm text-text-secondary", children: ["\u0422\u0435\u043A\u0443\u0449\u0438\u0439 email: ", _jsx("span", { className: "font-medium text-text-primary", children: user.email })] }), _jsx(Input, { label: "\u041D\u043E\u0432\u044B\u0439 email", type: "email", placeholder: "user@example.com", value: email, onChange: (e) => { setEmail(e.target.value); setError(""); }, error: error, autoFocus: true })] }) }));
}
