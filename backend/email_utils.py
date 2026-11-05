"""
Envio de e-mail via Brevo HTTP API (gratuito, funciona no Render free tier).
Configurar no Render: BREVO_API_KEY
Remetente verificado: mauricionimer1@gmail.com
"""
import os
import json
import urllib.request
from collections import deque
from datetime import datetime, timezone

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
SENDER_EMAIL  = "mauricionimer1@gmail.com"
SENDER_NAME   = "Mizan"


# Cabeçalho dos e-mails com a marca. Cliente de e-mail não mostra SVG (o Gmail
# bloqueia), então as três barras da logo são desenhadas com células de tabela,
# nas cores e proporções oficiais (design/logo).
CABECALHO_MARCA = (
    '<table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-table;'
    'background:#1a0033;border-radius:12px"><tr><td style="padding:12px 18px">'
    '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
    '<td style="vertical-align:bottom;padding-right:3px"><div style="width:6px;height:10px;background:#b8c0ee;border-radius:1px"></div></td>'
    '<td style="vertical-align:bottom;padding-right:3px"><div style="width:6px;height:15px;background:#8f9be9;border-radius:1px"></div></td>'
    '<td style="vertical-align:bottom;padding-right:10px"><div style="width:6px;height:20px;background:#5966d9;border-radius:1px"></div></td>'
    '<td style="vertical-align:bottom;color:#f4f2fa;font-family:Arial,sans-serif;font-size:22px;font-weight:bold;'
    'line-height:20px;letter-spacing:-0.5px">Mizan</td>'
    '</tr></table></td></tr></table>'
)


# Resultado dos últimos envios (sem destinatário nem assunto): alimenta o
# "Estado da plataforma" da Ajuda. Vive na memória do processo.
ENVIOS: deque = deque(maxlen=500)


def _anotar(ok: bool) -> bool:
    ENVIOS.append({"em": datetime.now(timezone.utc), "ok": ok})
    return ok


def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    if not BREVO_API_KEY:
        print("[Email] BREVO_API_KEY não configurado.")
        return False
    try:
        payload = json.dumps({
            "sender":      {"name": SENDER_NAME, "email": SENDER_EMAIL},
            "to":          [{"email": destinatario}],
            "subject":     assunto,
            "htmlContent": corpo_html,
        }).encode()
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "api-key":      BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[Email] Enviado para {destinatario} (status {resp.status})")
        return _anotar(True)
    except Exception as e:
        print(f"[Email] Erro: {e}")
        return _anotar(False)


def email_retreino(admin_email: str, treinadas: dict) -> bool:
    """Avisa que há versões novas, inativas, esperando o COMANDO conferir."""
    from html import escape
    itens = "".join(
        f"<p style='margin:4px 0;color:#475569'><strong>{escape(str(emp))}:</strong> "
        f"versão {escape(str(r.get('versao', '')))}, {int(r.get('novos') or 0)} pagamentos novos</p>"
        for emp, r in treinadas.items())
    assunto = f"[Mizan] {len(treinadas)} modelo(s) novo(s) aguardando conferência"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        {CABECALHO_MARCA}
      </div>
      <h2 style="color:#1e293b">Modelos novos treinados, ainda não ativos</h2>
      <p style="color:#475569">Cada empresa abaixo teve o próprio modelo treinado só com os pagamentos dela.</p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:20px 0">
        {itens}
      </div>
      <p style="color:#94a3b8;font-size:13px">Nada mudou nas análises. Confira as métricas e ative, se for o caso, em
      COMANDO → Treinar modelo de uma empresa.</p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
      <p style="color:#cbd5e1;font-size:12px;text-align:center">Mizan — Plataforma de análise de carteira de crédito com IA</p>
    </div>
    """
    return enviar_email(admin_email, assunto, corpo)


def email_drift(admin_email: str, score_atual: float, score_historico: float, n_dias: int = 30) -> bool:
    diff     = score_atual - score_historico
    direcao  = "queda" if diff < 0 else "aumento"
    cor_diff = "#ef4444" if diff < 0 else "#10b981"
    sinal    = "" if diff > 0 else ""
    assunto  = f"[Mizan] Alerta de drift — {direcao} de {abs(diff):.1f} pts no score médio"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        {CABECALHO_MARCA}
      </div>
      <h2 style="color:#1e293b">Alerta de drift detectado</h2>
      <p style="color:#475569">O score médio de recuperabilidade mudou significativamente nos últimos {n_dias} dias.</p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:20px 0">
        <p style="margin:4px 0;color:#475569"><strong>Score histórico:</strong> {score_historico:.1f}</p>
        <p style="margin:4px 0;color:#475569"><strong>Score recente ({n_dias}d):</strong> {score_atual:.1f}</p>
        <p style="margin:4px 0;color:{cor_diff}"><strong>Variação:</strong> {sinal}{diff:.1f} pontos</p>
      </div>
      <p style="color:#475569">Isso pode indicar mudança no perfil das carteiras ou necessidade de retreinamento.</p>
      <p style="color:#94a3b8;font-size:13px">Acesse o painel de IA para verificar a performance do modelo.</p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
      <p style="color:#cbd5e1;font-size:12px;text-align:center">Mizan — Plataforma de análise de carteira de crédito com IA</p>
    </div>
    """
    return enviar_email(admin_email, assunto, corpo)


def email_sync_mudancas(
    destinatario: str,
    nome_conexao: str,
    dados_novos: dict,
    dados_anteriores: dict | None = None,
    frontend_url: str = "https://mizan-sand.vercel.app",
) -> bool:
    total_novo  = dados_novos.get("total_devedores", 0) or 0
    score_novo  = float(dados_novos.get("score_medio", 0) or 0)
    valor_novo  = float(dados_novos.get("valor_face", 0) or 0)

    # Sem dados anteriores = primeiro sync com comparação impossível → não envia
    if not dados_anteriores:
        return False

    total_ant  = int(dados_anteriores.get("total_devedores", 0) or 0)
    score_ant  = float(dados_anteriores.get("score_medio", 0) or 0)
    novos      = total_novo - total_ant
    diff_score = score_novo - score_ant

    # Só notifica se houve mudança relevante
    tem_novos    = novos > 0
    score_mudou  = abs(diff_score) >= 2.0
    if not tem_novos and not score_mudou:
        print(f"[Email] Sync '{nome_conexao}' sem mudanças relevantes — email não enviado.")
        return False

    sinal_score = "▲" if diff_score > 0 else "▼"
    cor_score   = "#10b981" if diff_score > 0 else "#ef4444"
    bloco_novos = (
        f"<p style='margin:6px 0;color:#2563eb'><strong>+{novos} devedor{'es' if novos > 1 else ''} novo{'s' if novos > 1 else ''}</strong> detectado{'s' if novos > 1 else ''} na base.</p>"
        if tem_novos else ""
    )
    bloco_score = (
        f"<p style='margin:6px 0;color:{cor_score}'><strong>Score médio:</strong> {score_ant:.1f} → {score_novo:.1f} ({sinal_score} {abs(diff_score):.1f} pts)</p>"
        if score_mudou else
        f"<p style='margin:6px 0;color:#475569'><strong>Score médio:</strong> {score_novo:.1f}</p>"
    )

    assunto = f"[Mizan] {nome_conexao} — {'novos devedores detectados' if tem_novos else 'score alterado'}"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        {CABECALHO_MARCA}
      </div>
      <h2 style="color:#1e293b;margin-bottom:4px">Mudanças detectadas na carteira</h2>
      <p style="color:#64748b;margin-top:0">Conexão: <strong>{nome_conexao}</strong></p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:18px;margin:20px 0">
        {bloco_novos}
        {bloco_score}
        <p style="margin:6px 0;color:#475569"><strong>Total na carteira:</strong> {total_novo} devedores</p>
        <p style="margin:6px 0;color:#475569"><strong>Valor de face:</strong> R$ {valor_novo:,.0f}</p>
      </div>
      <div style="text-align:center;margin:28px 0">
        <a href="{frontend_url}" style="background:#2563eb;color:white;padding:13px 30px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px">
          Ver análise completa →
        </a>
      </div>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
      <p style="color:#cbd5e1;font-size:12px;text-align:center">Mizan — Plataforma de análise de carteira de crédito com IA</p>
    </div>
    """
    return enviar_email(destinatario, assunto, corpo)


def email_redefinir_senha(destinatario: str, nome: str, link: str) -> bool:
    assunto = "Redefinição de senha — Mizan"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        {CABECALHO_MARCA}
      </div>
      <h2 style="color:#1e293b">Olá, {nome}!</h2>
      <p style="color:#475569">Recebemos uma solicitação para redefinir a senha da sua conta.</p>
      <p style="color:#475569">Clique no botão abaixo para criar uma nova senha. O link expira em <strong>1 hora</strong>.</p>
      <div style="text-align:center;margin:32px 0">
        <a href="{link}" style="background:#2563eb;color:white;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px">
          Redefinir minha senha
        </a>
      </div>
      <p style="color:#94a3b8;font-size:13px">Se você não solicitou isso, ignore este e-mail. Sua senha não será alterada.</p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
      <p style="color:#cbd5e1;font-size:12px;text-align:center">Mizan — Plataforma de análise de carteira de crédito com IA</p>
    </div>
    """
    return enviar_email(destinatario, assunto, corpo)
