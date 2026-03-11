import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function Input({ label, error, className = "", ...props }) {
    return (_jsxs("div", { className: "flex flex-col gap-1", children: [label && _jsx("label", { className: "text-sm font-medium text-text-primary", children: label }), _jsx("input", { className: `w-full px-3 py-2 text-sm border rounded-lg outline-none transition-colors
          ${error ? "border-danger focus:ring-2 focus:ring-red-100" : "border-border focus:border-accent focus:ring-2 focus:ring-blue-100"}
          placeholder:text-text-secondary ${className}`, ...props }), error && _jsx("p", { className: "text-xs text-danger", children: error })] }));
}
