import { createContext, useContext, useState, useEffect } from 'react'

const Ctx = createContext(null)
const STORAGE_KEY = 'mizan_analysis'

export function AnalysisProvider({ children }) {
  const [result, setResultState] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) } catch { return null }
  })

  function setResult(val) {
    setResultState(val)
    if (val) {
      try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(val)) } catch {}
    } else {
      sessionStorage.removeItem(STORAGE_KEY)
    }
  }

  useEffect(() => {
    const clear = () => { setResultState(null); sessionStorage.removeItem(STORAGE_KEY) }
    window.addEventListener('mizan:logout', clear)
    return () => window.removeEventListener('mizan:logout', clear)
  }, [])

  return <Ctx.Provider value={{ result, setResult }}>{children}</Ctx.Provider>
}

export const useAnalysis = () => useContext(Ctx)
