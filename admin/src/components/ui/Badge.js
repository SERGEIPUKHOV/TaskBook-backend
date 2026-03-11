import { jsx as _jsx } from "react/jsx-runtime";
export function Badge({ active }) {
    return (_jsx("span", { className: `inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`, children: active ? "Активен" : "Заблокирован" }));
}
