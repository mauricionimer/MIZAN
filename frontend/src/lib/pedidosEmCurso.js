// Compartilha somente leituras simultâneas. Nenhum resultado fica em cache.
const pendentes = new Map()

export function invalidarLeiturasEmCurso() { pendentes.clear() }

export function leituraEmCurso(chave, executar) {
  if (pendentes.has(chave)) return pendentes.get(chave)
  const promessa = Promise.resolve().then(executar).finally(() => {
    // Uma escrita pode ter invalidado e iniciado outra leitura da mesma URL.
    if (pendentes.get(chave) === promessa) pendentes.delete(chave)
  })
  pendentes.set(chave, promessa)
  return promessa
}
