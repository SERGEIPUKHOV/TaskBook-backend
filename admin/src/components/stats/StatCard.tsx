interface StatCardProps {
  label: string
  value: number | string
  sub?: string
}

export function StatCard({ label, value, sub }: StatCardProps) {
  return (
    <div className="bg-white rounded-2xl border border-border p-5 flex flex-col gap-2">
      <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">{label}</span>
      <span className="text-3xl font-semibold text-text-primary tabular-nums">
        {typeof value === "number" ? value.toLocaleString("ru") : value}
      </span>
      {sub && <span className="text-xs text-text-secondary">{sub}</span>}
    </div>
  )
}
