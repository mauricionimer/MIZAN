"""
Envio de e-mail via Brevo HTTP API (gratuito, funciona no Render free tier).
Configurar no Render: BREVO_API_KEY
Remetente verificado: mauricionimer1@gmail.com
"""
import os
import json
import urllib.request

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
SENDER_EMAIL  = "mauricionimer1@gmail.com"
SENDER_NAME   = "Mizan"


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
        return True
    except Exception as e:
        print(f"[Email] Erro: {e}")
        return False


def email_retreino(admin_email: str, resultado: dict) -> bool:
    retrain   = resultado.get("retrain", {})
    versao    = retrain.get("versao", "nova versão")
    acc       = retrain.get("acuracia")
    n_fb      = resultado.get("n_feedbacks_novos", 0)
    acc_linha = f"<p style='margin:4px 0;color:#475569'><strong>Acurácia:</strong> {acc:.1%}</p>" if acc else ""
    assunto   = f"[Mizan] Modelo retreinado — {versao}"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        <div style="display:inline-block;background:#2563eb;border-radius:12px;padding:10px 18px">
          <span style="color:white;font-size:20px;font-weight:bold">⚖ Mizan</span>
        </div>
      </div>
      <h2 style="color:#1e293b">Modelo retreinado com sucesso</h2>
      <p style="color:#475569">O sistema de ML foi atualizado automaticamente com feedbacks reais.</p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:20px 0">
        <p style="margin:4px 0;color:#475569"><strong>Versão:</strong> {versao}</p>
        <p style="margin:4px 0;color:#475569"><strong>Feedbacks usados:</strong> {n_fb}</p>
        {acc_linha}
      </div>
      <p style="color:#94a3b8;font-size:13px">O modelo anterior foi substituído. Acesse o painel de IA para ver a performance.</p>
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
        <div style="display:inline-block;background:#2563eb;border-radius:12px;padding:10px 18px">
          <span style="color:white;font-size:20px;font-weight:bold">⚖ Mizan</span>
        </div>
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


def email_redefinir_senha(destinatario: str, nome: str, link: str) -> bool:
    assunto = "Redefinição de senha — Mizan"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        <div style="display:inline-block;background:#2563eb;border-radius:12px;padding:10px 18px">
          <span style="color:white;font-size:20px;font-weight:bold">⚖ Mizan</span>
        </div>
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
