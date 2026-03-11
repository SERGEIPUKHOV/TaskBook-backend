import { useCallback, useEffect, useState } from "react"
import { usersApi, type AdminUser, type UsersPage } from "../api/users"
import { UserTable } from "../components/users/UserTable"
import { UserSearchBar } from "../components/users/UserSearchBar"
import { BlockUserModal } from "../components/users/BlockUserModal"
import { ResetPasswordModal } from "../components/users/ResetPasswordModal"
import { SetEmailModal } from "../components/users/SetEmailModal"
import { Pagination } from "../components/ui/Pagination"
import { Toast, useToast } from "../components/ui/Toast"

const FRONTEND_URL = (import.meta.env.VITE_FRONTEND_URL as string | undefined) ?? "http://localhost:3001"

export function UsersPage() {
  const [data, setData] = useState<UsersPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [blockTarget, setBlockTarget] = useState<AdminUser | null>(null)
  const [blockLoading, setBlockLoading] = useState(false)
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null)
  const [emailTarget, setEmailTarget] = useState<AdminUser | null>(null)
  const { toast, show: showToast, hide: hideToast } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    usersApi.list({ page, per_page: 20, search: search || undefined })
      .then(setData)
      .catch(() => showToast("Ошибка загрузки", "error"))
      .finally(() => setLoading(false))
  }, [page, search, showToast])

  useEffect(() => { load() }, [load])

  const handleSearch = (v: string) => { setSearch(v); setPage(1) }

  const handleBlock = async (user: AdminUser) => {
    setBlockLoading(true)
    try {
      const updated = await usersApi.setActive(user.id, !user.is_active)
      setData((prev) => prev ? { ...prev, items: prev.items.map((u) => u.id === updated.id ? updated : u) } : prev)
      showToast(updated.is_active ? "Пользователь разблокирован" : "Пользователь заблокирован")
      setBlockTarget(null)
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", "error")
    } finally {
      setBlockLoading(false)
    }
  }

  const handleResetPassword = async (user: AdminUser): Promise<string> => {
    const result = await usersApi.resetPassword(user.id)
    showToast("Пароль сброшен")
    return result.temp_password
  }

  const handleSetEmail = async (user: AdminUser, email: string) => {
    const updated = await usersApi.setEmail(user.id, email)
    setData((prev) => prev ? { ...prev, items: prev.items.map((u) => u.id === updated.id ? updated : u) } : prev)
    showToast("Email обновлён")
  }

  const handleImpersonate = async (user: AdminUser) => {
    try {
      const { code } = await usersApi.impersonate(user.id)
      window.open(`${FRONTEND_URL}/auth/impersonate?code=${code}`, "_blank")
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", "error")
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-semibold text-text-primary">Пользователи</h2>
        <span className="text-sm text-text-secondary tabular-nums">{data?.total ?? "—"} всего</span>
      </div>

      <div className="bg-white rounded-2xl border border-border overflow-hidden shadow-sm">
        <div className="px-4 py-3 border-b border-border">
          <UserSearchBar value={search} onChange={handleSearch} />
        </div>
        <UserTable
          users={data?.items ?? []}
          loading={loading}
          onBlock={setBlockTarget}
          onResetPassword={setResetTarget}
          onSetEmail={setEmailTarget}
          onImpersonate={handleImpersonate}
        />
        <div className="px-4 border-t border-border">
          <Pagination page={page} total={data?.total ?? 0} perPage={20} onChange={setPage} />
        </div>
      </div>

      <BlockUserModal user={blockTarget} onClose={() => setBlockTarget(null)} onConfirm={handleBlock} loading={blockLoading} />
      <ResetPasswordModal user={resetTarget} onClose={() => setResetTarget(null)} onConfirm={handleResetPassword} />
      <SetEmailModal user={emailTarget} onClose={() => setEmailTarget(null)} onConfirm={handleSetEmail} />
      {toast && <Toast message={toast.message} type={toast.type} onClose={hideToast} />}
    </div>
  )
}
