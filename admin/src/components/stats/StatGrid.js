import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { StatCard } from "./StatCard";
export function StatGrid({ stats }) {
    return (_jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsx(StatCard, { label: "\u0412\u0441\u0435\u0433\u043E \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0435\u0439", value: stats.total_users }), _jsx(StatCard, { label: "\u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0445 \u0437\u0430 7 \u0434\u043D\u0435\u0439", value: stats.active_7d }), _jsx(StatCard, { label: "\u0412\u0441\u0435\u0433\u043E \u0437\u0430\u0434\u0430\u0447", value: stats.total_tasks }), _jsx(StatCard, { label: "\u0412\u0441\u0435\u0433\u043E \u043F\u0440\u0438\u0432\u044B\u0447\u0435\u043A", value: stats.total_habits })] }));
}
