import type { AdminUser } from "../../api/users"
import { UserRow } from "./UserRow"

interface Props {
  users: AdminUser[]
  onBlock: (user: AdminUser) => void
  onResetPassword: (user: AdminUser) => void
  onSetEmail: (user: AdminUser) => void
  onImpersonate: (user: AdminUser) => void
  loading: boolean
}

export function UserTable({ users, onBlock, onResetPassword, onSetEmail, onImpersonate, loading }: Props) {
  if (loading) return (
    <div className="flex justify-center py-12">
      <svg className="animate-spin h-6 w-6 text-accent" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
    </div>
  )

  if (users.length === 0) return (
    <p className="text-center py-12 text-sm text-text-secondary">Пользователи отсутствуют</p>
  )

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-border bg-surface">
            {["Email", "Статус", "Дата регистрации", "Задач", "Действие"].map((h) => (
              <th key={h} className="py-3 px-4 text-left text-xs font-semibold text-text-secondary uppercase tracking-wide">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <UserRow
              key={u.id}
              user={u}
              onBlock={onBlock}
              onResetPassword={onResetPassword}
              onSetEmail={onSetEmail}
              onImpersonate={onImpersonate}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
