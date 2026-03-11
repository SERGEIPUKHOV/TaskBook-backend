import type { ButtonHTMLAttributes } from "react"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "danger" | "ghost"
  size?: "sm" | "md"
  loading?: boolean
}

export function Button({ variant = "primary", size = "md", loading, className = "", children, disabled, ...props }: ButtonProps) {
  const base = "inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
  const variants = {
    primary: "bg-accent text-white hover:bg-blue-700 focus:ring-blue-500",
    danger:  "bg-danger text-white hover:bg-red-700 focus:ring-red-400",
    ghost:   "bg-transparent text-text-primary border border-border hover:bg-gray-50 focus:ring-gray-300",
  }
  const sizes = { sm: "px-3 py-1.5 text-xs gap-1.5", md: "px-4 py-2 text-sm gap-2" }
  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      )}
      {children}
    </button>
  )
}
