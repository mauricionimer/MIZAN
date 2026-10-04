import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, CheckCircle2, Send, Lightbulb, X } from 'lucide-react'
import AppShell from '../components/AppShell'
import DicaAjuda from '../components/DicaAjuda'
import { atualizarAvisosDeDuvida } from '../components/useAvisosDeDuvida'
import { useAuth } from '../context/AuthContext'
import { useAnalysis } from '../context/AnalysisContext'
import { listarDuvidasComando, responderDuvida, sugerirDuvida, revisarSugestao, listarLacunas, tratarLacuna, limparLacunas, publicarNoFaq } from '../api'

const ABAS = [
  { id: 'aberta',     rotulo: 'Abertas' },
  { id: 'respondida', rotulo: 'Respondidas' },
  { id: 'faq',        rotulo: 'No FAQ' },
  { id: 'sugestao',   rotulo: 'Sugestões para a Central' },
  { id: 'lacunas',    rotulo: 'Buscas sem resposta' },
]
const fmtData = (iso) => (iso ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso)) : '')

function Cartao({ d, token, aba, onMudou }) {
  const [resposta, setResposta] = useState(d.resposta || '')
  const [titulo, setTitulo]     = useState(d.sugestao_titulo || d.pergunta || '')
  const [editando, setEditando] = useState(d.estado === 'aberta')
  const [ocupado, setOcupado]   = useState(false)
  const [erro, setErro]         = useState('')

  async function agir(fn) {
    setOcupado(true); setErro('')
    try { await fn(); atualizarAvisosDeDuvida(); await onMudou() } catch (e) { setErro(e.message) } finally { setOcupado(false) }
  }

  return (
    <li className="rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-3">
        <span>{d.autor_nome || d.autor_email} · {d.empresa_id || 'COMANDO'} · {fmtData(d.created_at)}</span>
        {d.tela && <span className="font-mono">{d.tela}</span>}
      </div>
      <p className="mt-2 text-sm text-ink">{d.pergunta}</p>
      {d.buscou && d.buscou !== d.pergunta && <p className="mt-1 text-xs text-ink-3">Tinha buscado: "{d.buscou}"</p>}

      {editando ? (
        <div className="mt-3 space-y-2">
          <textarea value={resposta} onChange={e => setResposta(e.target.value)} rows={4} maxLength={4000}
            aria-label="Resposta" placeholder="Escreva a resposta. Quem perguntou a vê no menu Ajuda."
            className="w-full rounded-lg border border-line bg-page p-3 text-sm text-ink placeholder-ink-4 focus:border-blue-500/50 focus:outline-none" />
          <div className="flex gap-2">
            <button disabled={ocupado || resposta.trim().length < 2}
              onClick={() => agir(async () => { await responderDuvida(token, d.id, resposta.trim()); setEditando(false) })}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50">
              {ocupado ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              {d.estado === 'respondida' ? 'Salvar a correção' : 'Responder'}
            </button>
            {d.estado === 'respondida' && (
              <button onClick={() => { setEditando(false); setResposta(d.resposta || '') }} className="text-sm text-ink-3 hover:text-ink">Cancelar</button>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-3 rounded-lg bg-raise-1 p-3">
          <p className="section-label mb-1">Resposta · {d.respondida_por} · {fmtData(d.respondida_em)}</p>
          <p className="whitespace-pre-line text-sm leading-relaxed text-ink-2">{d.resposta}</p>
          <button onClick={() => setEditando(true)} className="mt-2 text-xs font-medium text-blue-400 hover:text-blue-300">Corrigir a resposta</button>
          {d.visto_em == null && <span className="ml-3 text-[11px] text-ink-3">ainda não vista por quem perguntou</span>}
        </div>
      )}

      {d.estado === 'respondida' && !editando && (
        <div className="mt-3 border-t border-line pt-3">
          {d.sugestao_estado == null && (
            <div className="space-y-2">
              <p className="text-[11px] text-ink-3">Dúvida recorrente? Publique no FAQ: todos os usuários veem a pergunta (este título) e a resposta, sem nome nem empresa.</p>
              <div className="flex flex-wrap items-center gap-2">
                <input value={titulo} onChange={e => setTitulo(e.target.value)} maxLength={200} aria-label="Pergunta no FAQ"
                  placeholder="Como a pergunta aparece no FAQ"
                  className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-page px-3 text-xs text-ink placeholder-ink-4" />
                <button disabled={ocupado || titulo.trim().length < 3} onClick={() => agir(() => publicarNoFaq(token, d.id, true, titulo.trim()))}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Publicar no FAQ
                </button>
                <button disabled={ocupado} onClick={() => agir(() => sugerirDuvida(token, d.id, true, titulo))}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-raise-2 px-3 py-2 text-xs font-medium text-ink hover:opacity-80 disabled:opacity-50">
                  <Lightbulb className="h-3.5 w-3.5" /> Revisar depois
                </button>
              </div>
            </div>
          )}
          {d.sugestao_estado === 'pendente' && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-ink-2">Sugerida para a Central{d.sugestao_titulo ? `: "${d.sugestao_titulo}"` : ''}. Revisão pendente.</span>
              <button disabled={ocupado} onClick={() => agir(() => publicarNoFaq(token, d.id, true, d.sugestao_titulo || titulo))}
                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 font-medium text-white hover:bg-emerald-500 disabled:opacity-50"><CheckCircle2 className="h-3.5 w-3.5" /> Publicar no FAQ</button>
              <button disabled={ocupado} onClick={() => agir(() => revisarSugestao(token, d.id, 'descartada'))}
                className="inline-flex items-center gap-1 rounded-lg bg-raise-2 px-3 py-1.5 font-medium text-ink hover:opacity-80 disabled:opacity-50"><X className="h-3.5 w-3.5" /> Descartar</button>
              <button disabled={ocupado} onClick={() => agir(() => sugerirDuvida(token, d.id, false))} className="text-ink-3 hover:text-ink">Retirar</button>
            </div>
          )}
          {d.sugestao_estado === 'aprovada' && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-emerald-500">No FAQ{d.sugestao_titulo ? `: "${d.sugestao_titulo}"` : ''} · por {d.sugestao_revisada_por}</span>
              <button disabled={ocupado} onClick={() => agir(() => publicarNoFaq(token, d.id, false))} className="text-ink-3 hover:text-ink">Tirar do FAQ</button>
            </div>
          )}
          {d.sugestao_estado === 'descartada' && <p className="text-xs text-ink-3">Sugestão descartada por {d.sugestao_revisada_por}.</p>}
        </div>
      )}
      {erro && <p className="mt-2 text-xs text-red-400" role="alert">{erro}</p>}
    </li>
  )
}

const NOMES_PERFIL = { operador: 'operador', admin: 'diretor', comando: 'COMANDO' }

function Lacunas({ token }) {
  const [estado, setEstado] = useState('pendentes')
  const [dados, setDados]   = useState(null)
  const [erro, setErro]     = useState('')
  const [ocupado, setOcupado] = useState('')

  const carregar = useCallback(async () => {
    setErro('')
    try { setDados(await listarLacunas(token, { estado })) } catch (e) { setErro(e.message) }
  }, [token, estado])
  useEffect(() => { setDados(null); carregar() }, [carregar])

  async function agir(chave, fn) {
    setOcupado(chave); setErro('')
    try { await fn(); await carregar() } catch (e) { setErro(e.message) } finally { setOcupado('') }
  }
  async function limpar() {
    if (!window.confirm('Apagar o registro de buscas com mais de 180 dias? Isso não pode ser desfeito.')) return
    await agir('limpar', () => limparLacunas(token, 180))
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-2">
        <DicaAjuda id="buscas-sem-resposta" /> Perguntas que a busca não soube responder, ou que a pessoa disse que não resolveram. Estão sem nome de
        usuário e sem empresa (só o perfil de quem buscou). Escreva a resposta no catálogo (backend/ajuda) e marque como tratada.
      </p>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {[['pendentes', 'Pendentes'], ['tratadas', 'Tratadas'], ['todas', 'Todas']].map(([id, r]) => (
          <button key={id} onClick={() => setEstado(id)}
            className={`rounded-lg px-3 py-1 ${estado === id ? 'bg-raise-2 text-ink' : 'text-ink-2 hover:bg-raise-1'}`}>{r}</button>
        ))}
        <button disabled={!!ocupado} onClick={limpar} className="ml-auto text-xs text-ink-3 hover:text-ink">Apagar registros com mais de 180 dias</button>
      </div>
      {erro && <p className="text-sm text-red-400" role="alert">{erro}</p>}
      {!dados && !erro && <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}
      {dados && dados.grupos.length === 0 && <p className="text-sm text-ink-3">Nada por aqui nos últimos {dados.dias} dias.</p>}
      {dados && dados.total_de_grupos > dados.grupos.length && (
        <p className="text-xs text-ink-3">Mostrando {dados.grupos.length} de {dados.total_de_grupos} perguntas.</p>
      )}
      <ul className="space-y-3">
        {dados?.grupos.map(g => (
          <li key={g.chave} className="rounded-xl border border-line bg-surface p-5">
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-3">
              <span className="rounded-full bg-blue-600 px-2 py-0.5 font-medium text-white">{g.total}×</span>
              <span>{g.sem_resposta} sem resposta · {g.nao_resolveu} "não resolveu"</span>
              <span>· {Object.entries(g.perfis).map(([p, n]) => `${NOMES_PERFIL[p] || p} ${n}`).join(', ')}</span>
              <span>· última {fmtData(g.ultima)}</span>
              {g.reapareceu && <span className="rounded-full bg-amber-500/15 px-2 py-0.5 font-medium text-amber-500">reapareceu depois de tratada</span>}
            </div>
            <p className="mt-2 text-sm text-ink">{g.exemplo}</p>
            {g.mais_perto && (
              <p className="mt-1 text-xs text-ink-3">
                Resposta mais próxima hoje: <Link className="text-blue-400 hover:text-blue-300" to={`/ajuda?id=${encodeURIComponent(g.mais_perto.id)}`}>{g.mais_perto.titulo}</Link>
              </p>
            )}
            {g.entradas_que_nao_resolveram.length > 0 && (
              <p className="mt-1 text-xs text-ink-3">
                Não resolveram: {g.entradas_que_nao_resolveram.map(e => `${e.id} (${e.vezes}×)`).join(', ')}
              </p>
            )}
            <button disabled={ocupado === g.chave} onClick={() => agir(g.chave, () => tratarLacuna(token, g.chave, !g.tratada))}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-raise-2 px-3 py-1.5 text-xs font-medium text-ink hover:opacity-80 disabled:opacity-50">
              <CheckCircle2 className="h-3.5 w-3.5" /> {g.tratada ? 'Reabrir' : 'Marcar como tratada'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function DuvidasComando() {
  const { token } = useAuth()
  const { result, setVista } = useAnalysis()
  const [aba, setAba]       = useState('aberta')
  const [dados, setDados]   = useState(null)
  const [erro, setErro]     = useState('')
  const [carregando, setCarregando] = useState(true)

  const carregar = useCallback(async () => {
    setErro('')
    try { setDados(await listarDuvidasComando(token, { estado: aba, limite: 50 })) }
    catch (e) { setErro(e.message) } finally { setCarregando(false) }
  }, [token, aba])

  useEffect(() => { if (aba === 'lacunas') { setCarregando(false); return } setCarregando(true); carregar() }, [carregar, aba])

  const contagem = (id) => (id === 'aberta' ? dados?.abertas : id === 'sugestao' ? dados?.sugestoes_pendentes : null)

  return (
    <AppShell secao="duvidas" onIrPara={setVista} temResultado={!!result} titulo="Dúvidas">
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <div>
          <p className="section-label">Central de ajuda</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">Dúvidas dos usuários<DicaAjuda id="responder-duvidas" /></h1>
          <p className="mt-1 text-sm text-ink-2">
            O que as pessoas não acharam na Central. A pergunta já vem sem CPF, CNPJ, telefone e e-mail, mas nomes
            podem ter passado: não copie a pergunta para fora do sistema.
          </p>
        </div>

        <div role="tablist" className="flex flex-wrap gap-2">
          {ABAS.map(a => (
            <button key={a.id} role="tab" aria-selected={aba === a.id} onClick={() => setAba(a.id)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${aba === a.id ? 'bg-raise-2 text-ink' : 'text-ink-2 hover:bg-raise-1'}`}>
              {a.rotulo}{contagem(a.id) > 0 && <span className="ml-1.5 rounded-full bg-blue-600 px-1.5 text-[11px] text-white">{contagem(a.id)}</span>}
            </button>
          ))}
        </div>

        {aba === 'lacunas' && <Lacunas token={token} />}
        {aba !== 'lacunas' && erro && <p className="text-sm text-red-400" role="alert">{erro}</p>}
        {aba !== 'lacunas' && carregando && <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 className="h-4 w-4 animate-spin" /> Carregando…</div>}
        {aba !== 'lacunas' && dados && !carregando && dados.itens.length === 0 && (
          <p className="text-sm text-ink-3">{aba === 'aberta' ? 'Nenhuma dúvida aberta. 🎉' : 'Nada por aqui.'}</p>
        )}
        {aba !== 'lacunas' && dados && (
          <ul className="space-y-3">
            {dados.itens.map(d => <Cartao key={d.id} d={d} token={token} aba={aba} onMudou={carregar} />)}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
