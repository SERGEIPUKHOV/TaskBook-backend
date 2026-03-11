import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
export function LoginPage() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await login(email, password);
            void navigate("/dashboard");
        }
        catch (err) {
            setError(err instanceof Error ? err.message : "Ошибка входа");
        }
        finally {
            setLoading(false);
        }
    };
    return (_jsx("div", { className: "min-h-screen bg-surface flex items-center justify-center", children: _jsxs("div", { className: "bg-white rounded-2xl shadow-panel p-8 w-full max-w-sm", children: [_jsxs("div", { className: "mb-6", children: [_jsx("h1", { className: "text-xl font-semibold text-text-primary", children: "TaskBook Admin" }), _jsx("p", { className: "text-sm text-text-secondary mt-1", children: "\u0423\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435 \u043F\u043B\u0430\u0442\u0444\u043E\u0440\u043C\u043E\u0439" })] }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsx(Input, { label: "Email", type: "email", value: email, onChange: (e) => setEmail(e.target.value), placeholder: "admin@taskbook.app", required: true, autoFocus: true }), _jsx(Input, { label: "\u041F\u0430\u0440\u043E\u043B\u044C", type: "password", value: password, onChange: (e) => setPassword(e.target.value), placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022", required: true }), error && _jsx("p", { className: "text-sm text-danger", children: error }), _jsx(Button, { type: "submit", className: "w-full", loading: loading, children: "\u0412\u043E\u0439\u0442\u0438" })] })] }) }));
}
