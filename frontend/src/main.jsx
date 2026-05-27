import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Quando o Vite faz deploy e os chunks mudam de hash,
// navegações client-side falham com ChunkLoadError.
// Aqui fazemos reload automático para carregar os novos chunks.
window.addEventListener('vite:preloadError', () => { window.location.reload() })

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
