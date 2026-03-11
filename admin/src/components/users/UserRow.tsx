import type { AdminUser } from "../../api/users"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"

interface Props {
  user: AdminUser
  onBlock: (user: AdminUser) => void
  onResetPassword: (user: AdminUser) => void
  onSetEmail: (user: AdminUser) => void
  onImpersonate: (user: AdminUser) => void
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "numeric" })
}

export function UserRow({ user, onBlock, onResetPassword, onSetEmail, onImpersonate }: Props) {
  return (
    <tr className="border-b border-border last:border-0 hover:bg-surface transition-colors">
      <td className="py-3 px-4 text-sm text-text-primary font-medium">{user.email}</td>
      <td className="py-3 px-4"><Badge active={user.is_active} /></td>
      <td className="py-3 px-4 text-sm text-text-secondary tabular-nums">{fmt(user.created_at)}</td>
      <td className="py-3 px-4 text-sm text-text-secondary tabular-nums">{user.tasks_count}</td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-1.5 justify-end flex-wrap">
          <Button variant="ghost" size="sm" onClick={() => onSetEmail(user)}>Email</Button>
          <Button variant="ghost" size="sm" onClick={() => onResetPassword(user)}>Пароль</Button>
          <Button variant="ghost" size="sm" onClick={() => onImpersonate(user)}>Войти</Button>
          <Button variant={user.is_active ? "danger" : "primary"} size="sm" onClick={() => onBlock(user)}>
            {user.is_active ? "Заблокировать" : "Разблокировать"}
          </Button>
        </div>
      </td>
    </tr>
  )
}
