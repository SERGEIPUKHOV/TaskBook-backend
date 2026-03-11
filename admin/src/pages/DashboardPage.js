import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { statsApi } from "../api/stats";
import { StatGrid } from "../components/stats/StatGrid";
export function DashboardPage() {
    const [stats, setStats] = useState(null);
    const [error, setError] = useState("");
    useEffect(() => {
        statsApi.get().then(setStats).catch(() => setError("Ошибка загрузки"));
    }, []);
    if (error)
        return _jsx("p", { className: "text-sm text-danger", children: error });
    if (!stats)
        return (_jsx("div", { className: "flex justify-center py-12", children: _jsxs("svg", { className: "animate-spin h-6 w-6 text-accent", viewBox: "0 0 24 24", fill: "none", children: [_jsx("circle", { className: "opacity-25", cx: "12", cy: "12", r: "10", stroke: "currentColor", strokeWidth: "4" }), _jsx("path", { className: "opacity-75", fill: "currentColor", d: "M4 12a8 8 0 018-8v8H4z" })] }) }));
    return (_jsxs("div", { className: "max-w-2xl", children: [_jsx("h2", { className: "text-base font-semibold text-text-primary mb-5", children: "\u041F\u043B\u0430\u0442\u0444\u043E\u0440\u043C\u0435\u043D\u043D\u0430\u044F \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430" }), _jsx(StatGrid, { stats: stats })] }));
}
