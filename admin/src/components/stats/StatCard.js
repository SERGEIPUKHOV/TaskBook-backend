import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function StatCard({ label, value, sub }) {
    return (_jsxs("div", { className: "bg-white rounded-2xl border border-border p-5 flex flex-col gap-2", children: [_jsx("span", { className: "text-xs font-medium text-text-secondary uppercase tracking-wide", children: label }), _jsx("span", { className: "text-3xl font-semibold text-text-primary tabular-nums", children: typeof value === "number" ? value.toLocaleString("ru") : value }), sub && _jsx("span", { className: "text-xs text-text-secondary", children: sub })] }));
}
