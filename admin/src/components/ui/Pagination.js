import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
export function Pagination({ page, total, perPage, onChange }) {
    const totalPages = Math.ceil(total / perPage);
    if (totalPages <= 1)
        return null;
    return (_jsxs("div", { className: "flex items-center justify-between py-3 px-1", children: [_jsxs("span", { className: "text-sm text-text-secondary tabular-nums", children: ["\u0421\u0442\u0440\u0430\u043D\u0438\u0446\u0430 ", page, " \u0438\u0437 ", totalPages, " \u00B7 ", total, " \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0435\u0439"] }), _jsxs("div", { className: "flex gap-2", children: [_jsx("button", { onClick: () => onChange(page - 1), disabled: page === 1, className: "px-3 py-1.5 text-sm border border-border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors", children: "\u2190 \u041D\u0430\u0437\u0430\u0434" }), _jsx("button", { onClick: () => onChange(page + 1), disabled: page >= totalPages, className: "px-3 py-1.5 text-sm border border-border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors", children: "\u0412\u043F\u0435\u0440\u0451\u0434 \u2192" })] })] }));
}
