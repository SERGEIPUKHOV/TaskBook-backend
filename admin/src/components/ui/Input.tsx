import type { InputHTMLAttributes } from "react"

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, className = "", ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-sm font-medium text-text-primary">{label}</label>}
      <input
        className={`w-full px-3 py-2 text-sm border rounded-lg outline-none transition-colors
          ${error ? "border-danger focus:ring-2 focus:ring-red-100" : "border-border focus:border-accent focus:ring-2 focus:ring-blue-100"}
          placeholder:text-text-secondary ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  )
}
