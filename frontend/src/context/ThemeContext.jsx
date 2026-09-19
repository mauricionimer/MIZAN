import { createContext, useContext, useEffect, useState, useCallback } from 'react'

const ThemeContext = createContext(null)
const CHAVE = 'mizan_tema'

// Lê a preferência salva. O index.html já aplicou o data-theme antes da
// primeira pintura; aqui só reconstruímos o mesmo estado no React.
function temaInicial() {
  try {
    const salvo = localStorage.getItem(CHAVE)
    if (salvo === 'light' || salvo === 'dark') return salvo
  } catch {
    /* localStorage bloqueado (modo privativo) — cai no padrão */
  }
  return 'dark'
}

export function ThemeProvider({ children }) {
  const [tema, setTema] = useState(temaInicial)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', tema)
    try { localStorage.setItem(CHAVE, tema) } catch { /* sem persistência */ }
  }, [tema])

  const alternar = useCallback(() => {
    setTema(t => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  return (
    <ThemeContext.Provider value={{ tema, alternar, claro: tema === 'light' }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme precisa estar dentro de ThemeProvider')
  return ctx
}
