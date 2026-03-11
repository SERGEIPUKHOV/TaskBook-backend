import { useEffect, useState } from "react"
import { Input } from "../ui/Input"

interface Props {
  value: string
  onChange: (v: string) => void
}

export function UserSearchBar({ value, onChange }: Props) {
  const [local, setLocal] = useState(value)

  useEffect(() => {
    const t = setTimeout(() => onChange(local), 400)
    return () => clearTimeout(t)
  }, [local, onChange])

  return (
    <div className="max-w-sm">
      <Input
        placeholder="Поиск по email..."
        value={local}
        onChange={(e) => setLocal(e.target.value)}
      />
    </div>
  )
}
