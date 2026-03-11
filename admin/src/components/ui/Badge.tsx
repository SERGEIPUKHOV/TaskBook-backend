export function Badge({ active }: { active: boolean }) {
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
      active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
    }`}>
      {active ? "Активен" : "Заблокирован"}
    </span>
  )
}
