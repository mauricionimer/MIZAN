const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

export async function analisarCarteira(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/analisar`, { method: 'POST', body: fd })
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: `Erro HTTP ${res.status}` }))
    throw new Error(detail)
  }
  return res.json()
}
