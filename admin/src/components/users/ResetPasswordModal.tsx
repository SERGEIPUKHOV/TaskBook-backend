import { useState } from "react"
import type { AdminUser } from "../../api/users"
import { Button } from "../ui/Button"
import { Modal } from "../ui/Modal"

interface Props {
  user: AdminUser | null
  onClose: () => void
  onConfirm: (user: AdminUser) => Promise<string>
}

export function ResetPasswordModal({ user, onClose, onConfirm }: Props) {
  const [loading, setLoading] = useState(false)
  const [tempPassword, setTempPassword] = useState<string | null>(null)

  const handleConfirm = async () => {
    if (!user) return
    setLoading(true)
    try {
      const pw = await onConfirm(user)
      setTempPassword(pw)
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => { setTempPassword(null); onClose() }

  if (!user) return null

  return (
    <Modal
      open={!!user}
      title="Сброс пароля"
      onClose={handleClose}
      footer={
        tempPassword ? (
          <Button variant="ghost" size="sm" onClick={handleClose}>Закрыть</Button>
        ) : (
          <>
            <Button variant="ghost" size="sm" onClick={handleClose} disabled={loading}>Отмена</Button>
            <Button variant="danger" size="sm" loading={loading} onClick={handleConfirm}>Сбросить пароль</Button>
          </>
        )
      }
    >
      {tempPassword ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-text-secondary">Временный пароль для <span className="font-medium text-text-primary">{user.email}</span>:</p>
          <code className="block bg-surface border border-border rounded-lg px-4 py-3 text-sm font-mono text-text-primary select-all">{tempPassword}</code>
          <p className="text-xs text-text-secondary">Скопируйте и передайте пользователю. Он сможет войти и сменить пароль.</p>
        </div>
      ) : (
        <p className="text-sm text-text-secondary">
          Сгенерировать временный пароль для{" "}
          <span className="font-medium text-text-primary">{user.email}</span>?
          Текущий пароль будет сброшен.
        </p>
      )}
    </Modal>
  )
}
