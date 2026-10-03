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
              texto: 'Coletamos dados de devedores fornecidos pela empresa contratante (CPF, nome, produto, valor da dívida, dias em atraso, renda estimada, UF), dados de acesso dos usuários do sistema (e-mail, nome, hash de senha), histórico de análises e registros de contatos realizados com devedores. Guardamos também as dúvidas que os usuários enviam ao COMANDO pela Central de Ajuda, com o nome e o e-mail de quem perguntou e a resposta recebida; CPF, CNPJ, telefone e e-mail digitados no texto são removidos automaticamente antes de gravar. Quando a busca da Central de Ajuda não encontra resposta (ou a pessoa diz que não resolveu), guardamos o texto buscado, já sem esses dados, e apenas o perfil de quem buscou (operador, diretor ou COMANDO), sem nome, e-mail ou empresa, para que o COMANDO escreva a resposta que faltou.',
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
              titulo: '6. Retenção e anonimização',
              texto: 'A empresa contratante define o prazo de retenção da própria carteira. Vencido o prazo, o CPF e o nome são removidos do registro e o restante da linha é mantido de forma anonimizada — o modelo continua aprendendo com o resultado (variáveis e se houve pagamento) sem que o registro aponte para uma pessoa. Enquanto a empresa não definir um prazo, os dados permanecem até que ela solicite a remoção ou o contrato seja encerrado, quando são eliminados. Ressalva honesta sobre o termo: remover CPF e nome de um registro que mantém UF, valor e dias em atraso é uma despersonalização forte, não uma garantia matemática de irreversibilidade — o cruzamento com uma base externa que já contenha esses campos pode, em tese, reidentificar. Para eliminação definitiva, o registro é apagado.',
            },
            {
              titulo: '7. Seus direitos (LGPD)',
              texto: 'Você tem direito a: confirmar a existência de tratamento; acessar seus dados; corrigir dados incompletos ou incorretos; solicitar anonimização ou exclusão; revogar consentimento; solicitar portabilidade; e pedir revisão de decisão automatizada (art. 20). O caminho depende de quem você é. Usuário do sistema: o botão "Deletar minha conta", em Alterar senha, remove a conta e os dados associados. Devedor: você não tem conta aqui — seus dados estão no sistema porque a instituição credora os enviou. O pedido é feito a ela, que dispõe da ferramenta para atendê-lo; a remoção do identificador é aplicada em todos os registros do seu CPF, independentemente de prazo.',
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
