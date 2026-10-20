import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true }, optimizeDeps: { noDiscovery: true, include: [] }, appType: 'custom', ssr: { noExternal: ['react-router-dom', 'react-router'], resolve: { conditions: ['import', 'module', 'development'] } } })
try {
  const { verificar } = await server.ssrLoadModule('/test_bento_render.jsx')
  verificar()
  console.log('Bento: dados, variantes, estados condicionais, progresso e links verificados.')
} finally {
  await server.close()
}
