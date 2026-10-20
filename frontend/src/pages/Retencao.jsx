import { useState, useEffect, useCallback } from 'react'
import {
  ShieldCheck, Loader2, AlertTriangle, CheckCircle2, UserX, Clock, Play,
} from 'lucide-react'
import AppShell from '../components/AppShell'
import { useConfirmar } from '../components/ConfirmarModal'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import {
  buscarRetencao, executarRetencao, eliminarTitular, putEmpresaConfig,
} from '../api'
import DicaAjuda from '../components/DicaAjuda'
import StatCard from '../components/StatCard'
import { KpiBento } from '../components/ui/stats-bento'

const fmt = (v) => new Intl.NumberFormat('pt-BR').format(v ?? 0)

const NOME_TABELA = {
  predicoes:     'Análises de devedores',
  feedbacks:     'Pagamentos registrados',
  contatos:      'Contatos realizados',
  recomendacoes: 'Recomendações da IA',
}

// Prazos que fazem sentido explicar, em vez de um campo numérico vazio onde
// o admin tem de inventar um número.
const SUGESTOES = [
  { dias: 180,  rotulo: '6 meses',  nota: 'Ciclo de cobrança encerrado' },
  { dias: 365,  rotulo: '1 ano',    nota: 'Cobre a fase especializada inteira' },
  { dias: 1825, rotulo: '5 anos',   nota: 'Alinha com a prescrição da dívida' },
]

function Cartao({ children, className = '' }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-6 ${className}`}>
      {children}
    </section>
  )
}

export default function Retencao() {
  const { pedir, modal } = useConfirmar()
  const { token } = useAuth()
  const { result, setVista } = useAnalysis()

  const [dados, setDados]       = useState(null)
  const [carregando, setCarreg] = useState(true)
  const [erro, setErro]         = useState('')
  const [aviso, setAviso]       = useState('')

  const [dias, setDias]         = useState(365)
  const [salvando, setSalvando] = useState(false)
  const [executando, setExec]   = useState(false)

  const [cpf, setCpf]           = useState('')
  const [eliminando, setElim]   = useState(false)
  // Retenção é do COMANDO, que age escolhendo a empresa.
  const [empresa, setEmpresa]   = useState('')
  const [empresas, setEmpresas] = useState([])
  const alvo = empresa.trim().toLowerCase()

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'}/comando/visao-geral`, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => (res.ok ? res.json() : null))
      .then(d => setEmpresas((d?.empresas || []).map(e => e.empresa_id).filter(Boolean)))
      .catch(() => {})
  }, [token])

  const carregar = useCallback(async () => {
    setErro('')
    if (!alvo) { setDados(null); setCarreg(false); return }
    try {
      const d = await buscarRetencao(token, alvo)
      setDados(d)
      setDias(d.politica?.ativa ? d.politica.dias : (d.prazo_simulado || 365))
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarreg(false)
    }
  }, [token, alvo])

  useEffect(() => { const t = setTimeout(carregar, 400); return () => clearTimeout(t) }, [carregar])

  async function salvarPrazo(ativa) {
    setSalvando(true); setErro(''); setAviso('')
    try {
      await putEmpresaConfig(token, { extra: { retencao: { ativa, dias: Number(dias) } } }, alvo)
      setAviso(ativa
        ? `Prazo de ${dias} dias salvo. Nada foi anonimizado ainda — use "Executar agora".`
        : 'Retenção desligada. Nenhum dado será anonimizado automaticamente.')
      await carregar()
    } catch (e) { setErro(e.message) } finally { setSalvando(false) }
  }

  async function executar() {
    const total = vencidasTotal
    const ok = await pedir({ titulo: `Anonimizar ${fmt(total)} registro(s)?`,
      texto: 'O CPF e o nome serão removidos definitivamente. O restante do registro permanece, e o modelo continua aprendendo com ele. Isto não pode ser desfeito.',
      confirmar: 'Anonimizar', perigo: true })
    if (!ok) return
    setExec(true); setErro(''); setAviso('')
    try {
      const r = await executarRetencao(token, alvo)
      setAviso(`${fmt(r.total)} registro(s) anonimizado(s).`)
      await carregar()
    } catch (e) { setErro(e.message) } finally { setExec(false) }
  }

  async function atenderTitular(e) {
    e.preventDefault()
    const ok = await pedir({ titulo: `Remover a identificação de ${cpf}?`,
      texto: 'Vale para todos os registros. Atende a um pedido de eliminação (LGPD art. 18) e não depende de prazo. Isto não pode ser desfeito.',
      confirmar: 'Remover identificação', perigo: true })
    if (!ok) return
    setElim(true); setErro(''); setAviso('')
    try {
      const r = await eliminarTitular(token, cpf, alvo)
      setAviso(r.total > 0
        ? `${fmt(r.total)} registro(s) deste titular foram anonimizados.`
        : 'Nenhum registro encontrado para este CPF nesta empresa.')
      setCpf('')
      await carregar()
    } catch (e) { setErro(e.message) } finally { setElim(false) }
  }

  const ativa = dados?.politica?.ativa
  const previa = dados?.previa || {}
  const vencidasTotal = Object.values(previa).reduce((s, p) => s + (p.vencidas || 0), 0)
  const identificadosTotal = dados?.total_com_identificacao ?? 0

  return (
    <AppShell secao="retencao" onIrPara={setVista} temResultado={!!result}
      titulo="Retenção de dados">
      <div className="mx-auto w-full max-w-3xl">

        <div className="mb-7">
          <p className="section-label">Privacidade</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">Retenção de dados<DicaAjuda id="retencao-de-dados" /></h1>
          <div className="mt-4 max-w-xs">
            <label htmlFor="ret-empresa" className="mb-1 block text-xs font-medium text-ink-2">Empresa</label>
            <input id="ret-empresa" list="ret-empresas" value={empresa} onChange={e => setEmpresa(e.target.value)}
              placeholder="ex.: goias_bank" className="w-full rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink" />
            <datalist id="ret-empresas">{empresas.map(e => <option key={e} value={e} />)}</datalist>
          </div>
        </div>

        {erro && (
          <div className="mb-5 flex items-start gap-2 rounded-xl px-4 py-3 text-sm text-red-400"
            style={{ background: 'rgb(var(--c-danger) / 0.08)', border: '1px solid rgb(var(--c-danger) / 0.18)' }}>
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{erro}</span>
          </div>
        )}
        {aviso && (
          <div className="mb-5 flex items-start gap-2 rounded-xl px-4 py-3 text-sm text-emerald-300"
            style={{ background: 'rgb(var(--c-success) / 0.08)', border: '1px solid rgb(var(--c-success) / 0.18)' }}>
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /><span>{aviso}</span>
          </div>
        )}

        {!alvo ? (
          <p className="text-sm text-ink-3">Escolha a empresa para ver e configurar a retenção dela.</p>
        ) : carregando ? (
          <div className="flex items-center justify-center gap-2 py-20" style={{ color: 'var(--ink-3)' }}>
            <Loader2 className="h-5 w-5 animate-spin" /> Carregando...
          </div>
        ) : !dados ? null : (
          <div className="space-y-5">

            {/* ── Situação ── */}
            <Cartao>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="section-label">Situação</p>
                  <h2 className="mt-0.5 text-sm font-semibold text-ink">
                    {ativa ? `Prazo de ${dados.politica.dias} dias em vigor` : 'Nenhum prazo configurado'}
                  </h2>
                  <p className="mt-1 text-xs" style={{ color: 'var(--ink-2)' }}>
                    {ativa
                      ? 'Registros mais antigos que o prazo perdem a identificação quando você executa.'
                      : 'Enquanto não houver prazo, nada é anonimizado. Os números abaixo são uma simulação.'}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                  ativa ? 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-300 ring-amber-500/20'}`}>
                  {ativa ? 'Configurado' : 'Desligado'}
                </span>
              </div>

              <KpiBento className="mt-5" aria-label="Resumo da retenção">
                <StatCard label="Registros com CPF hoje" value={fmt(identificadosTotal)} />
                <StatCard label={`Venceriam com ${ativa ? dados.politica.dias : dados?.prazo_simulado} dias`} value={fmt(vencidasTotal)} valueColor="var(--warning)" />
              </KpiBento>

              <table className="mt-4 w-full text-sm">
                <thead>
                  <tr className="border-b border-line">
                    <th className="pb-2 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ink-3)' }}>Onde</th>
                    <th className="pb-2 text-right text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ink-3)' }}>Com CPF</th>
                    <th className="pb-2 text-right text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ink-3)' }}>Vencidos</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(previa).map(([tabela, p]) => (
                    <tr key={tabela} className="border-b border-line last:border-0">
                      <td className="py-2.5" style={{ color: 'var(--ink-2)' }}>{NOME_TABELA[tabela] || tabela}</td>
                      <td className="tnum py-2.5 text-right text-ink">{fmt(p.com_identificacao)}</td>
                      <td className="tnum py-2.5 text-right" style={{ color: p.vencidas ? 'var(--warning)' : 'var(--ink-3)' }}>
                        {fmt(p.vencidas)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Cartao>

            {/* ── Definir o prazo ── */}
            <Cartao>
              <p className="section-label">Definir</p>
              <h2 className="mt-0.5 mb-1 text-sm font-semibold text-ink">Por quanto tempo guardar a identificação</h2>
              <p className="mb-4 text-xs" style={{ color: 'var(--ink-2)' }}>
                Entre {dados?.minimo_dias} dias e {Math.round((dados?.maximo_dias || 3650) / 365)} anos.
                Abaixo do mínimo o dado sairia antes de a cobrança terminar.
              </p>

              <div className="mb-4 flex flex-wrap gap-2">
                {SUGESTOES.map(({ dias: d, rotulo, nota }) => (
                  <button key={d} onClick={() => setDias(d)} title={nota}
                    className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                      Number(dias) === d
                        ? 'border-blue-500/50 bg-blue-500/10 text-blue-300'
                        : 'border-line text-ink-2 hover:bg-raise-2'}`}>
                    {rotulo}
                    <span className="ml-1.5" style={{ color: 'var(--ink-3)' }}>{nota}</span>
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>
                    Prazo em dias
                  </label>
                  <input type="number" min={dados?.minimo_dias || 30} max={dados?.maximo_dias || 3650}
                    value={dias} onChange={e => setDias(e.target.value)}
                    className="input-base w-36 tnum" />
                </div>
                <button onClick={() => salvarPrazo(true)} disabled={salvando}
                  className="btn-primary disabled:opacity-50">
                  {salvando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clock className="h-4 w-4" />}
                  {ativa ? 'Atualizar prazo' : 'Ativar retenção'}
                </button>
                {ativa && (
                  <button onClick={() => salvarPrazo(false)} disabled={salvando}
                    className="rounded-lg border border-line px-4 py-2 text-sm font-medium transition-colors hover:bg-raise-2 disabled:opacity-50"
                    style={{ color: 'var(--ink-2)' }}>
                    Desligar
                  </button>
                )}
              </div>

              <p className="mt-3 text-xs" style={{ color: 'var(--ink-3)' }}>
                Salvar o prazo não apaga nada. A anonimização só acontece quando você executa.
              </p>
            </Cartao>

            {/* ── Executar ── */}
            <Cartao>
              <p className="section-label">Executar</p>
              <h2 className="mt-0.5 mb-1 text-sm font-semibold text-ink">Anonimizar o que passou do prazo</h2>
              <p className="mb-4 text-xs" style={{ color: 'var(--ink-2)' }}>
                Remove CPF e nome dos registros vencidos. As variáveis que o modelo usa
                permanecem, então o aprendizado não se perde. <strong className="text-ink">Não pode ser desfeito.</strong>
              </p>
              <button onClick={executar} disabled={!ativa || executando || vencidasTotal === 0}
                className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-brand-ink transition-colors disabled:opacity-40"
                style={{ background: 'var(--warning)' }}>
                {executando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Executar agora ({fmt(vencidasTotal)})
              </button>
              {!ativa && (
                <p className="mt-2 text-xs" style={{ color: 'var(--ink-3)' }}>
                  Configure um prazo acima para habilitar.
                </p>
              )}
              {ativa && vencidasTotal === 0 && (
                <p className="mt-2 text-xs" style={{ color: 'var(--ink-3)' }}>
                  Nenhum registro venceu o prazo — nada a fazer por enquanto.
                </p>
              )}
            </Cartao>

            {/* ── Titular ── */}
            <Cartao>
              <p className="section-label">Pedido de titular</p>
              <h2 className="mt-0.5 mb-1 text-sm font-semibold text-ink">Um devedor pediu a exclusão dos dados<DicaAjuda id="pedido-do-titular" /></h2>
              <p className="mb-4 text-xs" style={{ color: 'var(--ink-2)' }}>
                Direito de eliminação (LGPD art. 18, V). Não depende de prazo: a
                identificação sai de todos os registros deste CPF hoje.
              </p>
              <form onSubmit={atenderTitular} className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>
                    CPF do titular
                  </label>
                  <input required value={cpf} onChange={e => setCpf(e.target.value)}
                    placeholder="000.000.000-00" className="input-base w-52 tnum" />
                </div>
                <button type="submit" disabled={eliminando || !cpf.trim()}
                  className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-300 transition-colors hover:bg-red-500/20 disabled:opacity-40">
                  {eliminando ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserX className="h-4 w-4" />}
                  Atender pedido
                </button>
              </form>
              <p className="mt-3 text-xs" style={{ color: 'var(--ink-3)' }}>
                A trilha de auditoria registra o atendimento com os quatro últimos dígitos,
                não o CPF inteiro — guardá-lo ali desfaria o que a ação acabou de fazer.
              </p>
            </Cartao>

            <p className="pb-2 text-xs leading-relaxed" style={{ color: 'var(--ink-3)' }}>
              <ShieldCheck className="mr-1 inline h-3.5 w-3.5" />
              Sobre o termo: remover CPF e nome de um registro que mantém UF, valor e dias
              em atraso é uma despersonalização forte, não uma garantia matemática de
              irreversibilidade. O cruzamento com uma base externa que já contenha esses
              campos pode, em tese, reidentificar.
            </p>
          </div>
        )}
      </div>
      {modal}
    </AppShell>
  )
}
