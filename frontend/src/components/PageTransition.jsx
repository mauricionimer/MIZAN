import { motion, useReducedMotion } from 'framer-motion'
import { pagina, SEM_MOVIMENTO } from '../lib/motion'

// Envolve cada rota. Quando o sistema operacional pede menos movimento,
// cai para um fade simples em vez de deslocar a página.
export default function PageTransition({ children }) {
  const reduzir = useReducedMotion()
  const v = reduzir ? SEM_MOVIMENTO : pagina

  return (
    <motion.div variants={v} initial="inicial" animate="entra" exit="sai">
      {children}
    </motion.div>
  )
}
