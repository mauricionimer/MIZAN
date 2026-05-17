import { createContext, useContext, useState } from 'react'

const Ctx = createContext(null)

export function AnalysisProvider({ children }) {
  const [result, setResult] = useState(null)
  return <Ctx.Provider value={{ result, setResult }}>{children}</Ctx.Provider>
}

export const useAnalysis = () => useContext(Ctx)
