interface PaginationProps {
  page: number
  total: number
  perPage: number
  onChange: (page: number) => void
}

export function Pagination({ page, total, perPage, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / perPage)
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between py-3 px-1">
      <span className="text-sm text-text-secondary tabular-nums">
        Страница {page} из {totalPages} · {total} пользователей
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page === 1}
          className="px-3 py-1.5 text-sm border border-border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
        >
          ← Назад
        </button>
        <button
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          className="px-3 py-1.5 text-sm border border-border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
        >
          Вперёд →
        </button>
      </div>
    </div>
  )
}
