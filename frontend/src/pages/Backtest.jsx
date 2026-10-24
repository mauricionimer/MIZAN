import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload as UploadIcon, Loader2, AlertTriangle, TrendingUp, TrendingDown,
} from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts'
import { rodarBacktest, traduzirErroRede } from '../api'
import DicaAjuda from '../components/DicaAjuda'
import IACalculando, { ETAPAS_BACKTEST } from '../components/IACalculando'
import AppShell from '../components/AppShell'

const fmtBRL = (v) => v != null
  ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
  : '—'
const fmtNum = (v) => v != null ? new Intl.NumberFormat('pt-BR').format(v) : '—'
// Sempre uma casa decimal: sem isso 56 e 40,1 ficam desalinhados na coluna.
const fmtPct1 = (v) => v == null ? '—' : `${Number(v).toFixed(1).replace('.', ',')}%`

// As capacidades chegam como chave de texto no JSON ("0.1", "0.2"…).
const CAPS = ['0.1', '0.2', '0.3', '0.5']
const CAP_PADRAO = '0.2'   // a capacidade típica de um ciclo de cobrança

// Duas séries com cor, validadas contra as duas superfícies do tema; o acaso
// e o teto entram como referência recessiva, não como concorrentes.
const COR_MIZAN = 'var(--chart-1)'
const COR_ATUAL = 'var(--chart-2)'
const COR_REF   = 'var(--ink-3)'

function Tile({ rotulo, valor, leitura, cor }) {
  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--raise-2)' }}>
      <p className="section-label mb-1">{rotulo}</p>
      <p className="text-2xl font-semibold tabular-nums" style={{ color: cor || 'var(--ink)' }}>{valor}</p>
      {leitura && <p className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>{leitura}</p>}
    </div>
  )
}

function DicaGrafico({ active, payload, label, sufixo = '' }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg px-3 py-2 text-xs shadow-lg"
      style={{ background: 'var(--raise-1)', border: '1px solid var(--line)' }}>
      <p className="font-semibold mb-1" style={{ color: 'var(--ink)' }}>{label}</p>
      {payload.map(p => (
        <p key={p.name} className="tabular-nums" style={{ color: 'var(--ink-2)' }}>
          <span className="inline-block h-2 w-2 rounded-sm mr-1.5" style={{ background: p.color }} />
          {p.name}: {p.value}{sufixo}
        </p>
      ))}
    </div>
  )
}

export default function Backtest() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [arquivo, setArquivo] = useState(null)
  const [rodando, setRodando] = useState(false)
  const [erro, setErro] = useState(null)
  const [r, setR] = useState(null)

  async function enviar(file) {
    if (!file) return
    setArquivo(file); setErro(null); setRodando(true); setR(null)
    try {
      setR(await rodarBacktest(file))
    } catch (e) {
      setErro(traduzirErroRede ? traduzirErroRede(e) : e.message)
    } finally {
      setRodando(false)
    }
  }

  // Com a ordem que o banco usou de verdade (coluna ordem_atual), a manchete
  // compara contra ela; sem, contra "maior dívida primeiro".
  const temFila = !!r?.ganho_sobre_fila_atual && !!r?.filas?.fila_atual
  const ganho = temFila ? r.ganho_sobre_fila_atual[CAP_PADRAO] : r?.ganho_sobre_pratica_atual?.[CAP_PADRAO]
  const venceu = ganho ? ganho.diferenca > 0 : null
  const capturaData = r ? CAPS.map(c => ({
    capacidade: `${Math.round(parseFloat(c) * 100)}%`,
    'Mizan': r.filas.mizan_ev[c]?.pct_capturado ?? 0,
    ...(temFila ? { 'Fila do banco': r.filas.fila_atual[c]?.pct_capturado ?? 0 } : {}),
    'Maior dívida': r.filas.maior_divida[c]?.pct_capturado ?? 0,
    'Acaso': r.filas.aleatorio[c]?.pct_capturado ?? 0,
    'Teto possível': r.filas.oraculo[c]?.pct_capturado ?? 0,
  })) : []

  return (
    <AppShell>
      <div className="w-full mx-auto max-w-5xl space-y-5">
        <h1 className="text-xl font-bold tracking-tight text-ink">Simulação histórica<DicaAjuda id="backtest" /></h1>
        {/* Entrada */}
        <section className="card p-5">
          <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>
            Suba uma carteira em que a cobrança <strong>já aconteceu</strong> e o desfecho é
            conhecido. O Mizan pontua como se fosse antes e compara a fila que teria formado
            com a que a operação usa hoje. Nada é gravado: a carteira entra para ser analisada,
            não para virar base.
          </p>
          <p className="text-sm leading-relaxed mt-2" style={{ color: 'var(--ink-2)' }}>
            Em resumo: o teste compara o que <strong>realmente aconteceu</strong> com o que o Mizan
            <strong> estimaria</strong> recuperar se tivesse priorizado a carteira. É uma medida do
            passado, não uma garantia de recuperação futura.
          </p>
          <p className="text-xs mt-2" style={{ color: 'var(--ink-3)' }}>
            Colunas obrigatórias: <code>cpf</code>, <code>valor_divida</code>,
            {' '}<code>dias_em_atraso</code>, <code>pagou</code>. Melhoram a análise:
            {' '}<code>valor_recuperado</code>, <code>renda_estimada</code>,
            {' '}<code>produto</code>, <code>uf</code> e <code>ordem_atual</code> — a ordem em que
            a equipe cobrou de verdade (1 = primeiro). Com ela, a comparação é contra a fila do
            próprio banco.
          </p>
          <div className="mt-4 flex items-center gap-3 flex-wrap">
            <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
              onChange={e => enviar(e.target.files?.[0])} />
            <button className="btn-primary" disabled={rodando}
              onClick={() => inputRef.current?.click()}>
              {rodando
                ? <><Loader2 className="h-4 w-4 animate-spin mr-2 inline" />Analisando…</>
                : <><UploadIcon className="h-4 w-4 mr-2 inline" />Escolher planilha</>}
            </button>
            {arquivo && <span className="text-sm" style={{ color: 'var(--ink-3)' }}>{arquivo.name}</span>}
          </div>
          {erro && (
            <div className="mt-4 flex items-start gap-2.5 rounded-xl p-3"
              style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--danger)' }} />
              <p className="text-sm" style={{ color: 'var(--ink-2)' }}>{erro}</p>
            </div>
          )}
          {rodando && <IACalculando etapas={ETAPAS_BACKTEST} titulo="A IA está testando a carteira histórica" compacto />}
        </section>

        {r && (
          <>
            {/* A manchete: ganho sobre a prática atual */}
            <section className="card p-5">
              <p className="section-label mb-2">
                {temFila
                  ? 'Trabalhando 20% da carteira, contra a fila que o banco usou'
                  : 'Trabalhando 20% da carteira, contra começar pela maior dívida'}
              </p>
              <div className="flex items-baseline gap-3 flex-wrap">
                {venceu ? <TrendingUp className="h-7 w-7" style={{ color: 'var(--success)' }} />
                        : <TrendingDown className="h-7 w-7" style={{ color: 'var(--danger)' }} />}
                <span className="text-4xl font-semibold tabular-nums"
                  style={{ color: venceu ? 'var(--success)' : 'var(--danger)' }}>
                  {ganho?.diferenca >= 0 ? '+' : '−'}{fmtBRL(Math.abs(ganho?.diferenca ?? 0))}
                </span>
                {ganho?.vantagem_pct != null && (
                  <span className="text-lg tabular-nums" style={{ color: 'var(--ink-3)' }}>
                    ({ganho.vantagem_pct > 0 ? '+' : '−'}{fmtPct1(Math.abs(ganho.vantagem_pct))})
                  </span>
                )}
              </div>
              <p className="text-sm mt-2 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                {venceu
                  ? (temFila
                      ? 'O Mizan recuperaria mais que a fila do banco, com a mesma capacidade de contato.'
                      : 'O Mizan recuperaria mais nesta carteira, com a mesma capacidade de contato.')
                  : (temFila
                      ? 'Nesta carteira, a fila que o banco usou recupera mais. O Mizan não teria vantagem aqui.'
                      : 'Nesta carteira, ordenar pela maior dívida recupera mais. O Mizan não teria vantagem aqui.')}
              </p>
            </section>

            {/* Separação e tamanho */}
            <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Tile rotulo="KS" valor={r.separacao?.ok === false ? '—' : r.separacao?.ks}
                leitura={r.separacao?.ks_leitura} />
              <Tile rotulo="Gini" valor={r.separacao?.ok === false ? '—' : r.separacao?.gini}
                leitura={r.separacao?.gini_leitura} />
              <Tile rotulo="Devedores" valor={fmtNum(r.n_devedores)}
                leitura={`${r.taxa_pagamento}% pagaram`} />
              <Tile rotulo="Recuperado" valor={fmtBRL(r.valor_recuperado)}
                leitura={`de ${fmtBRL(r.valor_face)} de face`} />
            </section>

            {r.separacao?.ks_leitura === 'suspeito' && (
              <div className="flex items-start gap-2.5 rounded-xl p-3.5"
                style={{ background: 'rgb(var(--c-warning) / 0.08)', border: '1px solid rgb(var(--c-warning) / 0.20)' }}>
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--warning)' }} />
                <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                  KS acima de 50 costuma indicar vazamento de dados — alguma coluna que já
                  carrega o desfecho —, não qualidade de modelo. Conferir se os campos são da
                  foto <strong>antes</strong> da cobrança começar.
                </p>
              </div>
            )}

            {/* Curva de captura */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--ink)' }}>
                Quanto se recupera trabalhando só o topo da fila
              </h2>
              <p className="text-xs mb-4" style={{ color: 'var(--ink-3)' }}>
                Percentual do total recuperável capturado, por capacidade de contato.
              </p>
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={capturaData} margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,141,166,0.22)" vertical={false} />
                    <XAxis dataKey="capacidade" tick={{ fontSize: 12, fill: 'var(--ink-3)' }}
                      axisLine={false} tickLine={false} />
                    <YAxis unit="%" tick={{ fontSize: 12, fill: 'var(--ink-3)' }}
                      axisLine={false} tickLine={false} domain={[0, 100]} />
                    <Tooltip content={<DicaGrafico sufixo="%" />} />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                      payload={[
                        { value: 'Mizan', type: 'line', color: COR_MIZAN },
                        ...(temFila ? [{ value: 'Fila do banco', type: 'line', color: COR_ATUAL }] : []),
                        { value: 'Maior dívida', type: 'line', color: temFila ? COR_REF : COR_ATUAL },
                        { value: 'Acaso', type: 'line', color: COR_REF },
                        { value: 'Teto possível', type: 'line', color: COR_REF },
                      ]} />
                    <Line type="monotone" dataKey="Teto possível" stroke={COR_REF} strokeWidth={1.5}
                      strokeDasharray="4 4" dot={false} />
                    <Line type="monotone" dataKey="Acaso" stroke={COR_REF} strokeWidth={1.5}
                      strokeDasharray="2 3" dot={false} />
                    {/* Com a fila do banco, "maior dívida" vira referência, como o acaso */}
                    <Line type="monotone" dataKey="Maior dívida" stroke={temFila ? COR_REF : COR_ATUAL}
                      strokeWidth={temFila ? 1.5 : 2} dot={temFila ? false : { r: 4 }} activeDot={{ r: 6 }} />
                    {temFila && (
                      <Line type="monotone" dataKey="Fila do banco" stroke={COR_ATUAL} strokeWidth={2}
                        dot={{ r: 4 }} activeDot={{ r: 6 }} />
                    )}
                    <Line type="monotone" dataKey="Mizan" stroke={COR_MIZAN} strokeWidth={2}
                      dot={{ r: 4 }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Os números exatos, para ler numa reunião */}
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: 'var(--ink-3)' }}>
                      <th className="text-left font-medium py-1.5">capacidade</th>
                      <th className="text-right font-medium">Mizan</th>
                      <th className="text-right font-medium">só score</th>
                      {temFila && <th className="text-right font-medium">fila do banco</th>}
                      <th className="text-right font-medium">maior dívida</th>
                      <th className="text-right font-medium">acaso</th>
                      <th className="text-right font-medium">teto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {CAPS.map(c => (
                      <tr key={c} style={{ borderTop: '1px solid var(--line)' }}>
                        <td className="py-1.5" style={{ color: 'var(--ink-2)' }}>
                          {Math.round(parseFloat(c) * 100)}% da base
                        </td>
                        <td className="text-right tabular-nums font-semibold" style={{ color: 'var(--ink)' }}>
                          {fmtPct1(r.filas.mizan_ev[c]?.pct_capturado)}
                        </td>
                        <td className="text-right tabular-nums" style={{ color: 'var(--ink-3)' }}>
                          {fmtPct1(r.filas.mizan_score[c]?.pct_capturado)}
                        </td>
                        {temFila && (
                          <td className="text-right tabular-nums" style={{ color: 'var(--ink-2)' }}>
                            {fmtPct1(r.filas.fila_atual[c]?.pct_capturado)}
                          </td>
                        )}
                        <td className="text-right tabular-nums" style={{ color: 'var(--ink-2)' }}>
                          {fmtPct1(r.filas.maior_divida[c]?.pct_capturado)}
                        </td>
                        <td className="text-right tabular-nums" style={{ color: 'var(--ink-3)' }}>
                          {fmtPct1(r.filas.aleatorio[c]?.pct_capturado)}
                        </td>
                        <td className="text-right tabular-nums" style={{ color: 'var(--ink-3)' }}>
                          {fmtPct1(r.filas.oraculo[c]?.pct_capturado)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Decis */}
            <section className="card p-5">
              <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--ink)' }}>
                Taxa de pagamento por decil de score
              </h2>
              <p className="text-xs mb-4" style={{ color: 'var(--ink-3)' }}>
                Num modelo que funciona, a taxa cai do primeiro decil para o décimo.
              </p>
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={r.decis} margin={{ top: 8, right: 8, left: -8, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,141,166,0.22)" vertical={false} />
                    <XAxis dataKey="decil" tick={{ fontSize: 12, fill: 'var(--ink-3)' }}
                      axisLine={false} tickLine={false} />
                    <YAxis unit="%" tick={{ fontSize: 12, fill: 'var(--ink-3)' }}
                      axisLine={false} tickLine={false} />
                    <Tooltip content={<DicaGrafico sufixo="%" />} cursor={{ fill: 'rgba(128,141,166,0.10)' }} />
                    <Bar dataKey="taxa_pagamento" name="Pagaram" fill={COR_MIZAN} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* O custo da escolha, quantificado */}
            {r.politicas?.custo_pct != null && (
              <section className="card p-5">
                <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--ink)' }}>
                  O custo da equidade
                </h2>
                <p className="text-xs mb-4" style={{ color: 'var(--ink-3)' }}>
                  Duas políticas de fila, lado a lado. Nenhuma é a certa: a escolha é do
                  comitê, e aqui ela aparece com o preço à vista.
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ color: 'var(--ink-3)' }}>
                        <th className="text-left font-medium py-1.5">política</th>
                        <th className="text-right font-medium">recupera</th>
                        <th className="text-right font-medium">paridade</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ['valor_esperado', 'Valor esperado (padrão)'],
                        ['proporcional_por_grupo', 'Proporcional por região'],
                      ].map(([k, rotulo]) => (
                        <tr key={k} style={{ borderTop: '1px solid var(--line)' }}>
                          <td className="py-2" style={{ color: 'var(--ink)' }}>{rotulo}</td>
                          <td className="text-right tabular-nums font-semibold" style={{ color: 'var(--ink)' }}>
                            {fmtBRL(r.politicas[k]?.recuperado)}
                          </td>
                          <td className="text-right tabular-nums"
                            style={{ color: (r.politicas[k]?.paridade ?? 0) >= 0.8
                              ? 'var(--success)' : 'var(--warning)' }}>
                            {r.politicas[k]?.paridade != null
                              ? `${(r.politicas[k].paridade * 100).toFixed(0)}%` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-sm mt-4 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                  Equalizar a atenção entre regiões custa{' '}
                  <strong>{fmtBRL(r.politicas.custo_da_equidade)}</strong>{' '}
                  ({fmtPct1(r.politicas.custo_pct)} da recuperação) nesta carteira.
                </p>
              </section>
            )}

            {/* Equidade — a pergunta que a área de compliance do banco faz */}
            {r.equidade?.ok && (
              <section className="card p-5">
                <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--ink)' }}>
                  Equidade entre regiões<DicaAjuda id="equidade" />
                </h2>
                <p className="text-xs mb-4" style={{ color: 'var(--ink-3)' }}>
                  A priorização trata as regiões de forma desigual? E, se trata, isso
                  acompanha diferença real de pagamento?
                </p>

                <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--ink-2)' }}>
                  {r.equidade.leitura}
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                  {[
                    ['Paridade demográfica', r.equidade.paridade_demografica,
                     'fatia priorizada de cada região'],
                    ['Igualdade de oportunidade', r.equidade.igualdade_oportunidade,
                     'entre quem pagou, fatia priorizada'],
                  ].map(([rotulo, m, ajuda]) => (
                    <div key={rotulo} className="rounded-xl p-4" style={{ background: 'var(--raise-2)' }}>
                      <p className="section-label mb-1">{rotulo}</p>
                      {m?.ok ? (
                        <>
                          <p className="text-2xl font-semibold tabular-nums"
                            style={{ color: m.acima_do_corte ? 'var(--success)' : 'var(--warning)' }}>
                            {(m.razao * 100).toFixed(0)}%
                          </p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>
                            {m.menos_favorecido} em relação a {m.mais_favorecido}
                          </p>
                        </>
                      ) : (
                        <p className="text-sm mt-1" style={{ color: 'var(--ink-3)' }}>
                          {m?.motivo ?? 'Exige o desfecho real para ser calculada.'}
                        </p>
                      )}
                      <p className="text-[11px] mt-2" style={{ color: 'var(--ink-3)' }}>{ajuda}</p>
                    </div>
                  ))}
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ color: 'var(--ink-3)' }}>
                        <th className="text-left font-medium py-1.5">região</th>
                        <th className="text-right font-medium">devedores</th>
                        <th className="text-right font-medium">priorizados</th>
                        <th className="text-right font-medium">fatia</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.equidade.paridade_demografica.grupos?.map(g => (
                        <tr key={g.grupo} style={{ borderTop: '1px solid var(--line)' }}>
                          <td className="py-1.5" style={{ color: 'var(--ink)' }}>
                            {g.grupo}
                            {g.amostra_pequena && (
                              <span className="ml-2 text-[10px] uppercase tracking-wide"
                                style={{ color: 'var(--ink-3)' }}>amostra pequena</span>
                            )}
                          </td>
                          <td className="text-right tabular-nums" style={{ color: 'var(--ink-2)' }}>
                            {fmtNum(g.n)}
                          </td>
                          <td className="text-right tabular-nums" style={{ color: 'var(--ink-2)' }}>
                            {fmtNum(g.selecionados)}
                          </td>
                          <td className="text-right tabular-nums font-semibold" style={{ color: 'var(--ink)' }}>
                            {fmtPct1(g.taxa * 100)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 space-y-2">
                  {r.equidade.avisos?.map((a, i) => (
                    <p key={i} className="text-xs leading-relaxed" style={{ color: 'var(--ink-3)' }}>{a}</p>
                  ))}
                </div>
              </section>
            )}

            {r.avisos?.length > 0 && (
              <section className="card p-5">
                <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ink)' }}>Ressalvas</h2>
                <div className="space-y-2.5">
                  {r.avisos.map((a, i) => (
                    <div key={i} className="flex items-start gap-2.5">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: 'var(--warning)' }} />
                      <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>{a}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}
