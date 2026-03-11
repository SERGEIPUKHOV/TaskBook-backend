import type { PlatformStats } from "../../api/stats"
import { StatCard } from "./StatCard"

export function StatGrid({ stats }: { stats: PlatformStats }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <StatCard label="Всего пользователей" value={stats.total_users} />
      <StatCard label="Активных за 7 дней" value={stats.active_7d} />
      <StatCard label="Всего задач" value={stats.total_tasks} />
      <StatCard label="Всего привычек" value={stats.total_habits} />
    </div>
  )
}
