import { useEffect } from 'react'

/**
 * Trava de saída: uma tela com alterações não salvas liga a trava, e quem
 * navega pelo app (o menu do AppShell) pergunta antes de sair. Fechar ou
 * recarregar a aba usa o aviso do próprio navegador.
 *
 * Limite conhecido: o botão "voltar" do navegador não é interceptado (o app usa
 * BrowserRouter, que não oferece bloqueio de navegação sem trocar o roteador).
 */
let trava = null

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
    return () => {
      window.removeEventListener('beforeunload', aviso)
      if (trava === minha) trava = null
    }
  }, [ativo, mensagem])
}
