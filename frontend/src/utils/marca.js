// Cor da empresa como superfície da marca (--royal: preenchimento de botão
// primário e afins). Usada pelo AuthContext (logado) e pelo Login (antes de
// entrar). Duas regras que não dá para ignorar:
//
// 1. A tinta por cima (--on-brand) é escolhida pela luminância da cor da
//    empresa. Cravar branco deixa texto ilegível sobre uma marca clara, e
//    cravar escuro faz o mesmo sobre uma marca escura.
// 2. --accent-text fica de fora de propósito. É o tom usado em ícone, link
//    e texto sobre fundo neutro, e precisa contrastar com a superfície, não
//    com a marca. Uma empresa de azul escuro sumia no tema escuro quando
//    essa cor era aplicada aqui.
const VARIAVEIS = ['--royal', '--royal-hover', '--royal-pressed', '--on-brand']

export function corValida(cor) {
  return typeof cor === 'string' && /^#[0-9a-f]{6}$/i.test(cor)
}

// Tinta que contrasta com a cor (true = clara).
export function tintaClaraPara(cor) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(cor.slice(i, i + 2), 16) / 255)
  const lin = v => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4))
  const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  const contraste = claro => {
    const [a, z] = claro ? [1.0, L] : [L, 0.0]
    return (Math.max(a, z) + 0.05) / (Math.min(a, z) + 0.05)
  }
  return contraste(true) >= contraste(false)
}

// Sem cor válida, remove tudo: cravar um valor no <html> venceria o --royal do
// tema escuro, que é mais claro que o do tema claro.
export function limparCorDaMarca(raiz = document.documentElement) {
  for (const v of VARIAVEIS) raiz.style.removeProperty(v)
}

export function aplicarCorDaMarca(cor, raiz = document.documentElement) {
  if (!corValida(cor)) { limparCorDaMarca(raiz); return }
  raiz.style.setProperty('--royal', cor)
  const tintaClara = tintaClaraPara(cor)
  raiz.style.setProperty('--on-brand', tintaClara ? '#ffffff' : '#0b1020')
  // Hover e pressed precisam sair da mesma cor, senão o estado herda o azul
  // do tema e a tinta escolhida acima deixa de contrastar. Com tinta clara
  // o botão escurece ao interagir; com tinta escura, clareia.
  const mover = f => {
    const alvo = tintaClara ? 0 : 255
    const canal = i => Math.round(parseInt(cor.slice(i, i + 2), 16) * (1 - f) + alvo * f)
    return `#${[1, 3, 5].map(i => canal(i).toString(16).padStart(2, '0')).join('')}`
  }
  raiz.style.setProperty('--royal-hover', mover(0.14))
  raiz.style.setProperty('--royal-pressed', mover(0.26))
}
