/** Uma atualização por vez; volta a consultar ao reabrir a aba. */
export function iniciarAtualizacaoVisivel(executar, {
  intervalo = 15000,
  maxErros = 3,
  documento = document,
  agendar = setTimeout,
  cancelar = clearTimeout,
} = {}) {
  let encerrado = false, ocupado = false, timer, erros = 0
  function limpar() { if (timer !== undefined) cancelar(timer); timer = undefined }
  async function atualizar() {
    limpar()
    if (encerrado || documento.hidden || ocupado || erros >= maxErros) return
    ocupado = true
    try { await executar(); erros = 0 } catch { erros++ }
    finally {
      ocupado = false
      if (!encerrado && !documento.hidden && erros < maxErros) timer = agendar(atualizar, intervalo)
    }
  }
  function visibilidade() {
    limpar()
    if (!documento.hidden) { erros = 0; void atualizar() }
  }
  documento.addEventListener('visibilitychange', visibilidade)
  void atualizar()
  return () => { encerrado = true; limpar(); documento.removeEventListener('visibilitychange', visibilidade) }
}
