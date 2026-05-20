"""
Envio de e-mail via Gmail SMTP usando smtplib (built-in Python).
Configurar no Render: GMAIL_USER e GMAIL_APP_PASSWORD.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER         = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")


def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[Email] GMAIL_USER ou GMAIL_APP_PASSWORD não configurados.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = f"Mizan <{GMAIL_USER}>"
        msg["To"]      = destinatario
        msg.attach(MIMEText(corpo_html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.ehlo()
            s.starttls()
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.sendmail(GMAIL_USER, destinatario, msg.as_string())
        print(f"[Email] Enviado para {destinatario}")
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
