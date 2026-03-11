import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../store/auth"
import { Input } from "../components/ui/Input"
import { Button } from "../components/ui/Button"

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await login(email, password)
      void navigate("/dashboard")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-panel p-8 w-full max-w-sm">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-text-primary">TaskBook Admin</h1>
          <p className="text-sm text-text-secondary mt-1">Управление платформой</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@taskbook.app" required autoFocus />
          <Input label="Пароль" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" className="w-full" loading={loading}>Войти</Button>
        </form>
      </div>
    </div>
  )
}
