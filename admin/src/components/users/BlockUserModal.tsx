import type { AdminUser } from "../../api/users"
import { Button } from "../ui/Button"
import { Modal } from "../ui/Modal"

interface Props {
  user: AdminUser | null
  onClose: () => void
  onConfirm: (user: AdminUser) => Promise<void>
  loading: boolean
}

export function BlockUserModal({ user, onClose, onConfirm, loading }: Props) {
  if (!user) return null
  const isBlocking = user.is_active
  return (
    <Modal
      open={!!user}
      title={isBlocking ? "Заблокировать пользователя" : "Разблокировать пользователя"}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={loading}>Отмена</Button>
          <Button variant={isBlocking ? "danger" : "primary"} size="sm" loading={loading} onClick={() => onConfirm(user)}>
            {isBlocking ? "Заблокировать" : "Разблокировать"}
          </Button>
        </>
      }
    >
      <p className="text-sm text-text-secondary">
        Вы уверены, что хотите {isBlocking ? "заблокировать" : "разблокировать"} пользователя{" "}
        <span className="font-medium text-text-primary">{user.email}</span>?
      </p>
    </Modal>
  )
}
