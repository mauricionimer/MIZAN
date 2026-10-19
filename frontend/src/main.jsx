import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Depois de um deploy os pedaços (chunks) mudam de nome e a navegação dentro
// do app falha ao baixar a tela. Recarrega para pegar os novos, no máximo uma
// vez a cada 10 s: se o arquivo faltar de verdade, não entra em laço.
window.addEventListener('vite:preloadError', (evento) => {
  const CHAVE = 'mizan_recarga_chunk'
  let ultima = 0
  try { ultima = Number(sessionStorage.getItem(CHAVE)) || 0 } catch { /* sem armazenamento */ }
  if (Date.now() - ultima < 10000) return   // deixa o erro seguir para a tela de erro
  evento.preventDefault()
  try { sessionStorage.setItem(CHAVE, String(Date.now())) } catch { /* sem armazenamento */ }
  window.location.reload()
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
