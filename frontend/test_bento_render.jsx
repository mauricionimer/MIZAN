import React from 'react'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import StatsBento from './src/components/ui/stats-bento'
import StatCard from './src/components/StatCard'

const render = content => renderToStaticMarkup(<StaticRouter location="/">{content}</StaticRouter>)
export function verificar() {
  const html = render(<StatsBento aria-label="Carteira">
    <StatCard label="Saldo" value="R$ 12.345.678,90" />
    {false && <StatCard label="Oculto" value={123} />}
    <StatCard label="Pagamentos" value={0} nota="Sem pagamentos" link={{ to: '/agenda', label: 'Abrir agenda' }} />
    <StatCard label="Meta" value="30%" barra={-1} />
    <StatCard label="Contatos" value={12} barra={2} />
  </StatsBento>)
  assert.equal((html.match(/bento-kpi--destaque/g) || []).length, 1)
  assert.equal((html.match(/bento-kpi--largo/g) || []).length, 1)
  assert.equal((html.match(/bento-kpi--pequeno/g) || []).length, 2)
  assert.match(html, /R\$ 12\.345\.678,90/)
  assert.match(html, />0<\/p>/)
  assert.match(html, /href="\/agenda"/)
  assert.match(html, /aria-valuenow="0"/)
  assert.match(html, /aria-valuenow="100"/)
  assert.doesNotMatch(html, /Oculto/)
  const par = render(<StatsBento><StatCard label="A" value={1} /><StatCard label="B" value={2} /></StatsBento>)
  assert.doesNotMatch(par, /bento-kpi--destaque/)
  assert.equal((par.match(/bento-kpi--pequeno/g) || []).length, 2)
}
