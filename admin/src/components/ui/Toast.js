import { jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
export function Toast({ message, type, onClose }) {
    const [visible, setVisible] = useState(true);
    useEffect(() => {
        const t = setTimeout(() => { setVisible(false); setTimeout(onClose, 300); }, 3000);
        return () => clearTimeout(t);
    }, [onClose]);
    return (_jsxs("div", { className: `fixed bottom-5 right-5 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-panel text-sm font-medium transition-all duration-300 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"} ${type === "success" ? "bg-white text-green-700 border border-green-200" : "bg-white text-danger border border-red-200"}`, children: [type === "success" ? "✓" : "✕", " ", message] }));
}
export function useToast() {
    const [toast, setToast] = useState(null);
    const show = (message, type = "success") => setToast({ message, type });
    const hide = () => setToast(null);
    return { toast, show, hide };
}
