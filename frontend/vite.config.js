import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')

  // Em produção, VITE_API_URL ausente não pode passar silenciosamente: o
  // bundle sairia apontando para 127.0.0.1 e o app subiria quebrado sem
  // nenhum erro visível. Melhor falhar aqui, no build.
  if (mode === 'production' && !env.VITE_API_URL) {
    throw new Error(
      'VITE_API_URL não definida. Configure-a nas variáveis de ambiente da ' +
      'plataforma (Vercel → Settings → Environment Variables) antes de publicar.'
    )
  }

  return { plugins: [react()] }
})
