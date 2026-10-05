import { useEffect } from 'react'

/**
 * Trava de saída: uma tela com alterações não salvas liga a trava, e quem
 * navega pelo app (o menu do AppShell) pergunta antes de sair. Fechar ou
 * recarregar a aba usa o aviso do próprio navegador.
 *
 * O botão "voltar" do navegador também é coberto: o BrowserRouter não permite
 * bloquear a navegação, então a tela empilha uma entrada de histórico igual à
 * atual; ao voltar, a entrada extra é reposta e o AppShell pergunta (evento
 * "mizan:voltar-bloqueado"). Confirmado, `confirmarVoltar` recua de verdade.
 */
let trava = null
let voltando = false
let ignorarAte = 0              // o recuo que a própria tela faz ao se limpar não conta como "voltar"
const SENTINELA = 'mizanSentinela'

export function confirmarVoltar() {
  voltando = true
  trava = null
  // Recua passando pelas entradas extras e pela própria tela (uma recarga com
  // alterações pendentes deixa mais de uma entrada igual no histórico).
  let passouTela = false
  const passo = () => {
    if (window.history.state?.[SENTINELA]) return window.history.back()
    if (!passouTela) { passouTela = true; return window.history.back() }
    window.removeEventListener('popstate', passo)
  }
  window.addEventListener('popstate', passo)
  window.history.back()
}

export function saidaTravada() {
  return trava
}

export function liberarSaida() {
  trava = null
}

export function useProtegerSaida(ativo, mensagem = 'Você tem alterações não salvas. Deseja sair?') {
  useEffect(() => {
    if (!ativo) return
    const minha = { mensagem }
    trava = minha
    const aviso = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', aviso)
    const empilhar = () => window.history.pushState({ ...window.history.state, [SENTINELA]: true }, '')
    const aoVoltar = () => {
      if (voltando || Date.now() < ignorarAte) return
      empilhar()                                        // fica na tela
      window.dispatchEvent(new Event('mizan:voltar-bloqueado'))
    }
    if (!window.history.state?.[SENTINELA]) empilhar()      // depois de recarregar, a entrada extra já existe
    window.addEventListener('popstate', aoVoltar)
    return () => {
      window.removeEventListener('beforeunload', aviso)
      window.removeEventListener('popstate', aoVoltar)
      if (trava === minha) trava = null
      // Salvou ou descartou e segue na tela: tira a entrada extra do histórico.
      if (!voltando && window.history.state?.[SENTINELA]) { ignorarAte = Date.now() + 500; window.history.back() }
      voltando = false
    }
  }, [ativo, mensagem])
}
