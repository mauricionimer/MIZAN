import ThemeToggle from '../components/ThemeToggle'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { LogoMark } from '../components/Logo'

export default function Privacidade() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen py-12 px-6">
      <ThemeToggle className="fixed top-4 right-4 z-50" />
      <div className="max-w-2xl mx-auto">
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-blue-400 hover:text-ink mb-8 transition-colors font-medium">
          <ArrowLeft className="h-4 w-4" /> Voltar
        </button>

        <div className="rounded-2xl p-8 space-y-6"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--line)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.50), 0 2px 8px rgba(0,0,0,0.30)',
          }}>
          <div className="flex items-center gap-3 mb-1">
            <LogoMark className="h-6 w-6 shrink-0" />
            <div>
              <h1 className="text-lg font-bold text-ink tracking-tight">Política de Privacidade</h1>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ink-3)' }}>
                Última atualização: maio de 2026 · Em conformidade com a LGPD (Lei nº 13.709/2018)
              </p>
            </div>
          </div>

          <div className="rounded-xl px-5 py-4 flex gap-3 items-start"
            style={{ background: 'rgb(var(--c-royal) / 0.08)', border: '1px solid rgb(var(--c-royal) / 0.20)' }}>
            <span className="text-blue-400 text-lg mt-0.5">🔒</span>
            <div>
              <p className="text-sm font-semibold text-blue-300">
                Dados armazenados em servidores no Brasil, em conformidade com a LGPD.
              </p>
              <p className="text-xs text-blue-400/70 mt-1">
                O banco de dados do Mizan opera na região AWS São Paulo (sa-east-1). Os arquivos enviados são processados exclusivamente para geração da análise e não são retidos após a conclusão.
              </p>
            </div>
          </div>

          <div className="border-t" style={{ borderColor: 'var(--line)' }} />

          {[
            {
              titulo: '1. Quem somos',
              texto: 'O Mizan é uma plataforma de análise de carteira de crédito com inteligência artificial, operada pela empresa contratante. Os dados processados pertencem aos clientes da empresa contratante e são utilizados exclusivamente para as finalidades descritas abaixo.',
            },
            {
              titulo: '2. Dados coletados',
              texto: 'Coletamos dados de devedores fornecidos pela empresa contratante (CPF, nome, produto, valor da dívida, dias em atraso, renda estimada, UF), dados de acesso dos usuários do sistema (e-mail, nome, hash de senha), histórico de análises e registros de contatos realizados com devedores.',
            },
            {
              titulo: '3. Finalidade do tratamento',
              texto: 'Os dados são utilizados para: (a) calcular score de recuperabilidade por machine learning; (b) recomendar estratégias de abordagem de cobrança; (c) retreinar o modelo com feedbacks reais; (d) gerar relatórios e exportações para a empresa contratante.',
            },
            {
              titulo: '4. Base legal',
              texto: 'O tratamento se baseia no legítimo interesse da empresa contratante na recuperação de crédito (art. 7º, IX da LGPD) e no cumprimento de obrigação contratual entre a empresa e seus clientes (art. 7º, V).',
            },
            {
              titulo: '5. Compartilhamento de dados',
              texto: 'Os dados são armazenados no Supabase (infraestrutura em nuvem). Não compartilhamos dados de devedores com terceiros. O acesso é restrito aos usuários cadastrados pela empresa contratante.',
            },
            {
              titulo: '6. Retenção',
              texto: 'Os dados são mantidos enquanto a conta da empresa estiver ativa. Após encerramento, os dados são excluídos em até 90 dias, exceto quando a retenção for exigida por lei.',
            },
            {
              titulo: '7. Seus direitos (LGPD)',
              texto: 'Você tem direito a: confirmar a existência de tratamento; acessar seus dados; corrigir dados incompletos ou incorretos; solicitar anonimização ou exclusão; revogar consentimento; solicitar portabilidade. Para exercer esses direitos, utilize o botão "Deletar minha conta" em Configurações ou entre em contato com o administrador do sistema.',
            },
            {
              titulo: '8. Segurança',
              texto: 'Adotamos criptografia de senhas (PBKDF2-HMAC-SHA256), criptografia de credenciais de banco de dados (AES via Fernet), autenticação JWT, rate limiting e controle de acesso por empresa. A comunicação é feita exclusivamente via HTTPS.',
            },
            {
              titulo: '9. Contato',
              texto: 'Para dúvidas sobre privacidade ou para exercer seus direitos, entre em contato com o administrador da sua empresa ou acesse as configurações do sistema.',
            },
          ].map(({ titulo, texto }) => (
            <div key={titulo}>
              <h2 className="text-sm font-semibold text-ink mb-1.5">{titulo}</h2>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>{texto}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
