import { useState } from "react"
import type { AdminUser } from "../../api/users"
import { Button } from "../ui/Button"
import { Input } from "../ui/Input"
import { Modal } from "../ui/Modal"

interface Props {
  user: AdminUser | null
  onClose: () => void
  onConfirm: (user: AdminUser, email: string) => Promise<void>
}

export function SetEmailModal({ user, onClose, onConfirm }: Props) {
  const [email, setEmail] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleClose = () => { setEmail(""); setError(""); onClose() }

  const handleConfirm = async () => {
    if (!user) return
    if (!email.includes("@")) { setError("Введите корректный email"); return }
    setLoading(true)
    try {
      await onConfirm(user, email)
      handleClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка")
    } finally {
      setLoading(false)
    }
  }

  if (!user) return null

  return (
    <Modal
      open={!!user}
      title="Изменить email"
      onClose={handleClose}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={handleClose} disabled={loading}>Отмена</Button>
          <Button size="sm" loading={loading} onClick={handleConfirm}>Сохранить</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-text-secondary">
          Текущий email: <span className="font-medium text-text-primary">{user.email}</span>
        </p>
        <Input
          label="Новый email"
          type="email"
          placeholder="user@example.com"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setError("") }}
          error={error}
          autoFocus
        />
      </div>
    </Modal>
  )
}
