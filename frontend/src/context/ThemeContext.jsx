import { createContext, useContext, useEffect, useState, useCallback } from 'react'

const ThemeContext = createContext(null)
const CHAVE = 'mizan_tema'

// Três estados, como pede o brief:
//   'sistema' -> nenhum data-theme no <html>; o CSS segue prefers-color-scheme
//   'light'   -> data-theme="light", claro forçado
//   'dark'    -> data-theme="dark", escuro forçado
// O index.html já aplicou o atributo antes da primeira pintura; aqui só
// reconstruímos o mesmo estado no React.
function preferenciaSalva() {
  try {
    const salvo = localStorage.getItem(CHAVE)
    if (salvo === 'light' || salvo === 'dark') return salvo
  } catch {
    /* localStorage bloqueado (modo privativo) — segue o sistema */
  }
  return 'sistema'
}

function sistemaEscuro() {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

export function ThemeProvider({ children }) {
  const [preferencia, setPreferencia] = useState(preferenciaSalva)
  const [escuroDoSistema, setEscuroDoSistema] = useState(sistemaEscuro)

  // Enquanto o usuário não escolher, o tema acompanha o sistema em tempo real.
  useEffect(() => {
    let mq
    try { mq = window.matchMedia('(prefers-color-scheme: dark)') } catch { return }
    const aoMudar = e => setEscuroDoSistema(e.matches)
    mq.addEventListener('change', aoMudar)
    return () => mq.removeEventListener('change', aoMudar)
  }, [])

  useEffect(() => {
    const raiz = document.documentElement
    if (preferencia === 'sistema') {
      raiz.removeAttribute('data-theme')
      try { localStorage.removeItem(CHAVE) } catch { /* sem persistência */ }
    } else {
      raiz.setAttribute('data-theme', preferencia)
      try { localStorage.setItem(CHAVE, preferencia) } catch { /* sem persistência */ }
    }
  }, [preferencia])

  const escuro = preferencia === 'dark' || (preferencia === 'sistema' && escuroDoSistema)

  // O toggle sempre sai do modo "sistema" e crava o oposto do que está valendo.
  const alternar = useCallback(() => {
    setPreferencia(escuro ? 'light' : 'dark')
  }, [escuro])

  return (
    <ThemeContext.Provider value={{ tema: escuro ? 'dark' : 'light', preferencia, alternar, claro: !escuro }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme precisa estar dentro de ThemeProvider')
  return ctx
}
