import { createContext, useContext, useState, useEffect } from 'react'

const Ctx = createContext(null)
const STORAGE_KEY = 'mizan_analysis'

export function AnalysisProvider({ children }) {
  const [result, setResultState] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) } catch { return null }
  })

  // Qual vista da tela única está aberta ("analise" ou "dashboard"). Fica
  // aqui, e não na página, para sobreviver a uma ida às telas que ainda têm
  // rota própria — o usuário volta onde estava.
  const [vista, setVista] = useState(null)

  function setResult(val) {
    setResultState(val)
    if (val) {
      try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(val)) } catch {}
    } else {
      sessionStorage.removeItem(STORAGE_KEY)
    }
  }

  useEffect(() => {
    const clear = () => { setResultState(null); setVista(null); sessionStorage.removeItem(STORAGE_KEY) }
    window.addEventListener('mizan:logout', clear)
    return () => window.removeEventListener('mizan:logout', clear)
  }, [])

  return <Ctx.Provider value={{ result, setResult, vista, setVista }}>{children}</Ctx.Provider>
}

export const useAnalysis = () => useContext(Ctx)
