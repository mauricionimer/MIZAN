import { useEffect, useRef } from 'react'

// Pilha de modais abertos: Esc fecha só o de cima (um modal aberto sobre outro
// não pode fechar os dois com uma tecla).
const pilha = []

const FOCAVEIS = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Comportamento comum dos modais do Mizan:
 *  - Esc fecha (só o modal do topo);
 *  - Tab/Shift+Tab ficam presos dentro do modal;
 *  - o foco entra no modal (em `focoInicial`, se existir; senão no primeiro
 *    campo) e volta ao elemento que abriu quando fecha;
 *  - a página atrás não rola.
 *
 * Uso: const caixa = useModal(aberto, onFechar); <div ref={caixa} role="dialog" aria-modal …>
 * `focoInicial`: seletor CSS dentro do modal (ex.: o botão seguro de uma confirmação).
 */
export default function useModal(aberto, onFechar, { focoInicial } = {}) {
  const caixa = useRef(null)
  const fechar = useRef(onFechar)
  fechar.current = onFechar

  useEffect(() => {
    if (!aberto) return
    const anterior = document.activeElement
    const meu = {}
    pilha.push(meu)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const t = setTimeout(() => {
      const el = caixa.current
      if (!el || el.contains(document.activeElement)) return
      const alvo = (focoInicial && el.querySelector(focoInicial)) || el.querySelector(FOCAVEIS) || el
      if (alvo === el) el.setAttribute('tabindex', '-1')
      alvo.focus()
    }, 30)

    const tecla = (e) => {
      if (pilha[pilha.length - 1] !== meu) return
      if (e.key === 'Escape') { e.stopPropagation(); fechar.current?.(); return }
      if (e.key === 'Tab' && caixa.current) {
        const foc = [...caixa.current.querySelectorAll(FOCAVEIS)].filter(x => x.offsetParent !== null)
        if (!foc.length) { e.preventDefault(); return }
        const i = foc.indexOf(document.activeElement)
        if (e.shiftKey && i <= 0) { e.preventDefault(); foc[foc.length - 1].focus() }
        else if (!e.shiftKey && (i === -1 || i === foc.length - 1)) { e.preventDefault(); foc[0].focus() }
      }
    }
    window.addEventListener('keydown', tecla, true)
    return () => {
      clearTimeout(t)
      window.removeEventListener('keydown', tecla, true)
      const k = pilha.indexOf(meu)
      if (k >= 0) pilha.splice(k, 1)
      document.body.style.overflow = pilha.length ? 'hidden' : overflow
      anterior?.focus?.()
    }
  }, [aberto])        // eslint-disable-line react-hooks/exhaustive-deps

  return caixa
}
