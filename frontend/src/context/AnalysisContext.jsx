import { createContext, useContext, useState, useEffect } from 'react'

const Ctx = createContext(null)

export function AnalysisProvider({ children }) {
  const [result, setResult] = useState(null)
  useEffect(() => {
    const clear = () => setResult(null)
    window.addEventListener('mizan:logout', clear)
    return () => window.removeEventListener('mizan:logout', clear)
  }, [])
  return <Ctx.Provider value={{ result, setResult }}>{children}</Ctx.Provider>
}

export const useAnalysis = () => useContext(Ctx)
