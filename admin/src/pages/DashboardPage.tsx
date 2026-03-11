import { useEffect, useState } from "react"
import { statsApi, type PlatformStats } from "../api/stats"
import { StatGrid } from "../components/stats/StatGrid"

export function DashboardPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    statsApi.get().then(setStats).catch(() => setError("Ошибка загрузки"))
  }, [])

  if (error) return <p className="text-sm text-danger">{error}</p>
  if (!stats) return (
    <div className="flex justify-center py-12">
      <svg className="animate-spin h-6 w-6 text-accent" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
    </div>
  )

  return (
    <div className="max-w-2xl">
      <h2 className="text-base font-semibold text-text-primary mb-5">Платформенная статистика</h2>
      <StatGrid stats={stats} />
    </div>
  )
}
