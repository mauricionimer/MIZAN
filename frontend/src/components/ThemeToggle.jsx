import { Sun, Moon } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

export default function ThemeToggle({ className = '' }) {
  const { claro, alternar } = useTheme()
  const rotulo = claro ? 'Mudar para tema escuro' : 'Mudar para tema claro'

  return (
    <button
      type="button"
      onClick={alternar}
      title={rotulo}
      aria-label={rotulo}
      className={`p-1.5 rounded-lg text-ink-2 hover:text-ink hover:bg-raise-2 transition-colors ${className}`}
    >
      {claro ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
    </button>
  )
}
