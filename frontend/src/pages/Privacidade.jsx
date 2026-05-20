import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function Privacidade() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen bg-slate-50 py-12 px-6">
      <div className="max-w-2xl mx-auto">
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-8">
          <ArrowLeft className="h-4 w-4" /> Voltar
        </button>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 space-y-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-white text-sm font-bold">⚖</span>
            </div>
            <h1 className="text-xl font-bold text-slate-800">Política de Privacidade</h1>
          </div>
          <p className="text-xs text-slate-400">Última atualização: maio de 2026 · Em conformidade com a LGPD (Lei nº 13.709/2018)</p>

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
              <h2 className="text-sm font-semibold text-slate-700 mb-1.5">{titulo}</h2>
              <p className="text-sm text-slate-500 leading-relaxed">{texto}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
