import { useEffect, useState } from "react"

export type ToastType = "success" | "error"

interface ToastProps {
  message: string
  type: ToastType
  onClose: () => void
}

export function Toast({ message, type, onClose }: ToastProps) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const t = setTimeout(() => { setVisible(false); setTimeout(onClose, 300) }, 3000)
    return () => clearTimeout(t)
  }, [onClose])

  return (
    <div className={`fixed bottom-5 right-5 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-panel text-sm font-medium transition-all duration-300 ${
      visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
    } ${type === "success" ? "bg-white text-green-700 border border-green-200" : "bg-white text-danger border border-red-200"}`}>
      {type === "success" ? "✓" : "✕"} {message}
    </div>
  )
}

export function useToast() {
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null)
  const show = (message: string, type: ToastType = "success") => setToast({ message, type })
  const hide = () => setToast(null)
  return { toast, show, hide }
}
