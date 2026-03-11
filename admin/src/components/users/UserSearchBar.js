import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Input } from "../ui/Input";
export function UserSearchBar({ value, onChange }) {
    const [local, setLocal] = useState(value);
    useEffect(() => {
        const t = setTimeout(() => onChange(local), 400);
        return () => clearTimeout(t);
    }, [local, onChange]);
    return (_jsx("div", { className: "max-w-sm", children: _jsx(Input, { placeholder: "\u041F\u043E\u0438\u0441\u043A \u043F\u043E email...", value: local, onChange: (e) => setLocal(e.target.value) }) }));
}
