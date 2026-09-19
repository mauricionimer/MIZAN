// Variantes compartilhadas de animação.
// Duração curta de propósito: a navegação tem que parecer fluida, não lenta.

export const TRANSICAO = { duration: 0.22, ease: [0.22, 1, 0.36, 1] }

// Entrada/saída de página
export const pagina = {
  inicial: { opacity: 0, y: 8 },
  entra:   { opacity: 1, y: 0, transition: TRANSICAO },
  sai:     { opacity: 0, y: -6, transition: { duration: 0.14, ease: 'easeIn' } },
}

// Container que escalona a entrada dos filhos
export const lista = {
  inicial: {},
  entra: { transition: { staggerChildren: 0.045, delayChildren: 0.04 } },
}

// Item de uma lista escalonada
export const item = {
  inicial: { opacity: 0, y: 10 },
  entra:   { opacity: 1, y: 0, transition: TRANSICAO },
}

// Usado quando o sistema pede menos movimento: só fade, sem deslocamento
export const SEM_MOVIMENTO = {
  inicial: { opacity: 0 },
  entra:   { opacity: 1, transition: { duration: 0.12 } },
  sai:     { opacity: 0, transition: { duration: 0.1 } },
}
