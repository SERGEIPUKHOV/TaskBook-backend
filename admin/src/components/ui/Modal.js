import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from "react";
export function Modal({ open, title, onClose, children, footer }) {
    useEffect(() => {
        if (!open)
            return;
        const onKey = (e) => { if (e.key === "Escape")
            onClose(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [open, onClose]);
    if (!open)
        return null;
    return (_jsxs("div", { className: "fixed inset-0 z-50 flex items-center justify-center", children: [_jsx("div", { className: "absolute inset-0 bg-black/40 backdrop-blur-sm", onClick: onClose }), _jsxs("div", { className: "relative bg-white rounded-2xl shadow-panel w-full max-w-md mx-4 overflow-hidden", children: [_jsx("div", { className: "px-6 py-4 border-b border-border", children: _jsx("h2", { className: "text-base font-semibold text-text-primary", children: title }) }), _jsx("div", { className: "px-6 py-4", children: children }), footer && (_jsx("div", { className: "px-6 py-4 border-t border-border flex justify-end gap-2", children: footer }))] })] }));
}
