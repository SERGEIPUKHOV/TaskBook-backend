import { useAuth } from "../../store/auth"
import { Button } from "../ui/Button"

export function Topbar({ title }: { title: string }) {
  const { logout } = useAuth()
  return (
    <header className="h-14 bg-white border-b border-border flex items-center justify-between px-6 shrink-0">
      <h1 className="text-sm font-semibold text-text-primary">{title}</h1>
      <Button variant="ghost" size="sm" onClick={logout}>Выйти</Button>
    </header>
  )
}
