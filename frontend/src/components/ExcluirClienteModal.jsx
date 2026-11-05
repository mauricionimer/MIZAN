import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, Loader2, CheckCircle2 } from 'lucide-react'
import useModal from './useModal'
import { excluirClienteETudo } from '../api'

// Rótulo de cada tabela no resumo do que foi apagado.
const ROTULOS = {
  usuarios: 'usuários', carteiras: 'carteiras', predicoes: 'devedores', feedbacks: 'feedbacks',
  agente_casos: 'casos dos agentes', agente_mensagens: 'mensagens', agente_eventos: 'eventos',
  agente_passos: 'passos dos agentes', agente_logs: 'registros dos agentes', conexoes_db: 'conexões',
  conexao_permissoes: 'permissões de conexão', api_keys: 'chaves de API', agenda: 'itens de agenda',
  acordo_parcelas: 'parcelas de acordos', ofertas_feitas: 'ofertas', contatos: 'contatos',
  roteiros: 'roteiros', recomendacoes: 'recomendações', modelos_arquivos: 'arquivos de modelo',
}

/**
 * Excluir um cliente e TODOS os dados dele (só COMANDO). Não dá para desfazer.
 * Travas (guia de design, seção 9): marcar que entende + nome digitado + senha (+ código do
 * aplicativo, se ligado) + segundo clique em até 5 s.
 */
export default function ExcluirClienteModal({ aberto, token, empresaId, nome, totalUsuarios, onFechar, onExcluido }) {
  const caixa = useModal(aberto, onFechar, { focoInicial: '[data-seguro]' })
  const [entendo, setEntendo] = useState(false)
  const [digitado, setDigitado] = useState('')
  const [senha, setSenha] = useState('')
  const [codigo, setCodigo] = useState('')
  const [armado, setArmado] = useState(false)          // primeiro clique feito; vale 5 s
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')
  const [feito, setFeito] = useState(null)
  const timer = useRef(null)

  useEffect(() => () => clearTimeout(timer.current), [])
  useEffect(() => {
    if (aberto) return
    // fechou: limpa tudo (a senha não fica na memória da tela)
    setEntendo(false); setDigitado(''); setSenha(''); setCodigo(''); setArmado(false); setErro(''); setFeito(null)
  }, [aberto])

  const nomeCerto = digitado.trim().toLowerCase() === String(nome).trim().toLowerCase()
    || digitado.trim().toLowerCase() === String(empresaId).trim().toLowerCase()
  const pronto = entendo && nomeCerto && senha.length > 0 && !ocupado

  async function clicar() {
    if (!pronto) return
    if (!armado) {
      setArmado(true)
      timer.current = setTimeout(() => setArmado(false), 5000)
      return
    }
    clearTimeout(timer.current)
    setOcupado(true); setErro('')
    try {
      const r = await excluirClienteETudo(token, empresaId, { confirmacao: digitado, senha, codigo })
      setFeito(r)
      setSenha(''); setCodigo('')
    } catch (e) {
      setErro(e.message || 'Não foi possível excluir agora.')
      setArmado(false)
    } finally {
      setOcupado(false)
    }
  }

  const resumo = feito ? Object.entries(feito.apagados || {}).map(([k, v]) => `${v} ${ROTULOS[k] || k.replaceAll('_', ' ')}`) : []

  return createPortal(
    aberto ? (
      <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        onClick={feito ? () => onExcluido?.() : onFechar}>
        <div ref={caixa} role="alertdialog" aria-modal="true" aria-labelledby="excluir-cliente-titulo"
          onClick={e => e.stopPropagation()}
          className="w-full max-w-md max-h-[92vh] overflow-y-auto rounded-2xl p-5 shadow-2xl"
          style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
          {feito ? (
            <div className="text-center py-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{ background: 'rgb(var(--c-success) / 0.12)', border: '1px solid rgb(var(--c-success) / 0.20)' }}>
                <CheckCircle2 className="w-7 h-7 text-emerald-400" aria-hidden="true" />
              </div>
              <h2 id="excluir-cliente-titulo" className="text-base font-bold" style={{ color: 'var(--ink)' }}>Cliente excluído</h2>
              <p className="mt-2 text-sm" style={{ color: 'var(--ink-2)' }}>
                {resumo.length ? `Apagados: ${resumo.join(', ')}.` : 'Não havia dados para apagar.'}
              </p>
              <p className="mt-2 text-xs" style={{ color: 'var(--ink-3)' }}>
                A trilha de auditoria fica, sem o e-mail das pessoas.
              </p>
              <button type="button" data-seguro onClick={() => onExcluido?.()} className="btn-primary mt-5 w-full min-h-[44px]">Fechar</button>
            </div>
          ) : (
            <>
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--danger)' }} aria-hidden="true" />
                <div>
                  <h2 id="excluir-cliente-titulo" className="text-base font-bold" style={{ color: 'var(--ink)' }}>
                    Excluir “{nome}” e todos os dados?
                  </h2>
                  <p className="mt-1 text-sm" style={{ color: 'var(--ink-2)' }}>
                    Apaga carteiras, devedores, conversas e registros dos agentes, conexões, chaves de API, acordos, configurações
                    e os {totalUsuarios} usuário(s) deste cliente. <strong>Não dá para desfazer.</strong>
                  </p>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <label className="flex items-start gap-2 text-sm cursor-pointer" style={{ color: 'var(--ink)' }}>
                  <input type="checkbox" checked={entendo} onChange={e => { setEntendo(e.target.checked); setArmado(false) }} className="mt-1" />
                  Entendo que não dá para desfazer
                </label>
                <div>
                  <label htmlFor="excluir-nome" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                    Para confirmar, digite: <span className="font-mono" style={{ color: 'var(--ink)' }}>{nome}</span>
                  </label>
                  <input id="excluir-nome" className="input-base" autoComplete="off" value={digitado}
                    onChange={e => { setDigitado(e.target.value); setArmado(false) }} />
                </div>
                <div>
                  <label htmlFor="excluir-senha" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>Sua senha</label>
                  <input id="excluir-senha" type="password" className="input-base" autoComplete="current-password" value={senha}
                    onChange={e => { setSenha(e.target.value); setArmado(false) }} />
                </div>
                <div>
                  <label htmlFor="excluir-codigo" className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--ink-2)' }}>
                    Código de 6 dígitos do aplicativo
                  </label>
                  <input id="excluir-codigo" className="input-base tracking-widest text-center" inputMode="numeric" autoComplete="one-time-code"
                    placeholder="000000" value={codigo} onChange={e => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))} />
                </div>
              </div>

              {erro && (
                <div role="alert" className="mt-3 text-sm rounded-xl px-4 py-3"
                  style={{ color: 'var(--danger)', background: 'rgb(var(--c-danger) / 0.10)', border: '1px solid rgb(var(--c-danger) / 0.20)' }}>
                  {erro}
                </div>
              )}

              <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
                <button type="button" onClick={clicar} disabled={!pronto}
                  className="btn-danger min-h-[44px] disabled:opacity-40" style={{ color: '#fff' }}>
                  {ocupado ? <><Loader2 className="h-4 w-4 animate-spin" /> Excluindo…</>
                    : armado ? 'Clique de novo para excluir definitivamente' : 'Excluir tudo'}
                </button>
                <button type="button" data-seguro onClick={onFechar} className="btn-primary min-h-[44px]">Cancelar</button>
              </div>
            </>
          )}
        </div>
      </div>
    ) : null,
    document.body)
}
