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
