"""
JobAgent — Módulo 4: Notificação por Email
- Lê vagas aprovadas do Módulo 3
- Monta email HTML profissional
- Envia via Gmail SMTP
- Aguarda resposta "APLICAR" para acionar o Módulo 5
"""

import json
import smtplib
import imaplib
import email
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────
# CONFIGURAÇÃO DE EMAIL
# ─────────────────────────────────────────

def carregar_credenciais(path: str = "credenciais.json") -> dict:
    """
    Carrega email + senha de app do Gmail.
    NUNCA commitar esse arquivo — adicionar ao .gitignore.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️  credenciais.json não encontrado.")
        print("    Crie o arquivo com o seguinte formato:")
        print("""
    {
      "email_remetente": "seubot@gmail.com",
      "senha_app": "xxxx xxxx xxxx xxxx",
      "email_destinatario": "seu@email.com"
    }
        """)
        print("    Gere a senha em: https://myaccount.google.com/apppasswords")
        return {}


# ─────────────────────────────────────────
# TEMPLATE HTML DO EMAIL
# ─────────────────────────────────────────

CORES_PLATAFORMA = {
    "LinkedIn":  {"bg": "#0077b5", "text": "#fff"},
    "Indeed":    {"bg": "#2164f3", "text": "#fff"},
    "Gupy":      {"bg": "#00c853", "text": "#fff"},
    "Glassdoor": {"bg": "#0caa41", "text": "#fff"},
}

ICONE_NIVEL = {
    "Estágio": "🟡",
    "Júnior":  "🟢",
    "Pleno":   "🔵",
    "Sênior":  "🔴",
}

ICONE_MODALIDADE = {
    "Remoto":     "🏠",
    "Híbrido":    "🔀",
    "Presencial": "🏢",
}


def card_vaga_html(vaga: dict, index: int) -> str:
    cor = CORES_PLATAFORMA.get(vaga.get("plataforma", ""), {"bg": "#6b7280", "text": "#fff"})
    nivel_icon = ICONE_NIVEL.get(vaga.get("nivel", ""), "⚪")
    modal_icon = ICONE_MODALIDADE.get(vaga.get("modalidade", ""), "📍")
    salario = vaga.get("salario") or "Não informado"
    nivel = vaga.get("nivel") or "Não informado"
    modalidade = vaga.get("modalidade") or "Não informado"

    return f"""
    <tr>
      <td style="padding: 0 0 16px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="
          background: #ffffff;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        ">
          <!-- HEADER DA PLATAFORMA -->
          <tr>
            <td style="
              background: {cor['bg']};
              padding: 10px 18px;
              color: {cor['text']};
              font-size: 11px;
              font-weight: 700;
              letter-spacing: 1px;
              text-transform: uppercase;
            ">
              {vaga.get('plataforma', '')} &nbsp;·&nbsp; Vaga #{index}
            </td>
          </tr>

          <!-- TÍTULO + EMPRESA -->
          <tr>
            <td style="padding: 18px 18px 8px;">
              <div style="font-size: 17px; font-weight: 700; color: #111827; margin-bottom: 4px;">
                {vaga.get('titulo', '')}
              </div>
              <div style="font-size: 14px; color: #6b7280;">
                {vaga.get('empresa', 'Empresa não informada')}
              </div>
            </td>
          </tr>

          <!-- BADGES -->
          <tr>
            <td style="padding: 0 18px 14px;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding-right: 8px;">
                    <span style="
                      background: #f3f4f6; color: #374151;
                      padding: 4px 10px; border-radius: 20px;
                      font-size: 12px; font-weight: 500;
                    ">{nivel_icon} {nivel}</span>
                  </td>
                  <td style="padding-right: 8px;">
                    <span style="
                      background: #f3f4f6; color: #374151;
                      padding: 4px 10px; border-radius: 20px;
                      font-size: 12px; font-weight: 500;
                    ">{modal_icon} {modalidade}</span>
                  </td>
                  <td>
                    <span style="
                      background: #ecfdf5; color: #065f46;
                      padding: 4px 10px; border-radius: 20px;
                      font-size: 12px; font-weight: 500;
                    ">💰 {salario}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- LOCALIZAÇÃO -->
          <tr>
            <td style="padding: 0 18px 14px; font-size: 12px; color: #9ca3af;">
              📍 {vaga.get('localizacao', 'Não informado')}
            </td>
          </tr>

          <!-- BOTÃO -->
          <tr>
            <td style="padding: 0 18px 18px;">
              <a href="{vaga.get('url', '#')}" style="
                display: inline-block;
                background: #111827;
                color: #ffffff;
                padding: 9px 20px;
                border-radius: 8px;
                text-decoration: none;
                font-size: 12px;
                font-weight: 600;
              ">Ver vaga →</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    """


def montar_email_html(vagas: list[dict], config: dict) -> str:
    """Monta o HTML completo do email de notificação."""
    total = len(vagas)
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    cards = "".join(card_vaga_html(v, i + 1) for i, v in enumerate(vagas))

    plataformas = list({v.get("plataforma", "") for v in vagas})
    plataformas_str = " · ".join(plataformas)

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- HEADER -->
          <tr>
            <td style="
              background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
              border-radius: 16px 16px 0 0;
              padding: 32px;
              text-align: center;
            ">
              <div style="font-size: 28px; margin-bottom: 8px;">🤖</div>
              <div style="color: #fff; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">
                JobAgent encontrou {total} vaga{'s' if total != 1 else ''}!
              </div>
              <div style="color: rgba(255,255,255,0.75); font-size: 13px; margin-top: 6px;">
                {data_hora} · {plataformas_str}
              </div>
            </td>
          </tr>

          <!-- INSTRUÇÃO DE APROVAÇÃO -->
          <tr>
            <td style="
              background: #fffbeb;
              border: 1px solid #fde68a;
              padding: 16px 24px;
              text-align: center;
              font-size: 13px;
              color: #92400e;
            ">
              💡 Para aplicar em <strong>todas as vagas abaixo</strong>, responda este email com <strong>APLICAR</strong><br>
              Para selecionar vagas específicas, responda com os números: ex. <strong>APLICAR 1,3</strong>
            </td>
          </tr>

          <!-- CARDS DE VAGAS -->
          <tr>
            <td style="background:#f9fafb;padding:24px 16px 0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                {cards}
              </table>
            </td>
          </tr>

          <!-- STATS -->
          <tr>
            <td style="background:#f9fafb;padding:0 16px 24px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="
                background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;
              ">
                <tr>
                  <td align="center" style="border-right:1px solid #e5e7eb;padding:8px 0;">
                    <div style="font-size:22px;font-weight:800;color:#4f46e5;">{total}</div>
                    <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;">Compatíveis</div>
                  </td>
                  <td align="center" style="border-right:1px solid #e5e7eb;padding:8px 0;">
                    <div style="font-size:22px;font-weight:800;color:#059669;">{len([v for v in vagas if v.get('modalidade') == 'Remoto'])}</div>
                    <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;">Remotas</div>
                  </td>
                  <td align="center" style="padding:8px 0;">
                    <div style="font-size:22px;font-weight:800;color:#d97706;">{len(plataformas)}</div>
                    <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;">Plataformas</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="
              background:#111827;
              border-radius:0 0 16px 16px;
              padding:20px;
              text-align:center;
              font-size:11px;
              color:#6b7280;
            ">
              JobAgent · Próxima busca em {config.get('frequencia_horas', 2)}h<br>
              <span style="color:#4b5563;">Para parar o agente, responda: PAUSAR</span>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
    """


def montar_email_texto(vagas: list[dict]) -> str:
    """Versão plaintext do email (fallback)."""
    linhas = [
        f"JobAgent — {len(vagas)} vaga(s) encontrada(s)",
        f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "=" * 50,
        "",
        "Para aplicar em todas, responda: APLICAR",
        "Para vagas específicas: APLICAR 1,3",
        "",
    ]
    for i, v in enumerate(vagas, 1):
        linhas += [
            f"{i}. [{v.get('plataforma')}] {v.get('titulo')} — {v.get('empresa')}",
            f"   📍 {v.get('localizacao')}",
            f"   💰 {v.get('salario') or 'N/A'}  |  📈 {v.get('nivel') or 'N/A'}  |  🏠 {v.get('modalidade') or 'N/A'}",
            f"   🔗 {v.get('url')}",
            "",
        ]
    return "\n".join(linhas)


# ─────────────────────────────────────────
# ENVIO DE EMAIL
# ─────────────────────────────────────────

def enviar_email(vagas: list[dict], config: dict, credenciais: dict) -> bool:
    """Envia o email de notificação via Gmail SMTP."""
    if not credenciais:
        print("❌ Credenciais não configuradas.")
        return False

    remetente = credenciais["email_remetente"]
    senha = credenciais["senha_app"]
    destinatario = credenciais.get("email_destinatario") or config.get("email")

    if not destinatario:
        print("❌ Email destinatário não configurado.")
        return False

    total = len(vagas)
    assunto = f"🤖 JobAgent — {total} vaga{'s' if total != 1 else ''} compatível{'is' if total != 1 else ''} encontrada{'s' if total != 1 else ''}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"]    = f"JobAgent <{remetente}>"
    msg["To"]      = destinatario
    msg["Reply-To"] = destinatario

    # Adiciona versão texto e HTML
    msg.attach(MIMEText(montar_email_texto(vagas), "plain", "utf-8"))
    msg.attach(MIMEText(montar_email_html(vagas, config), "html", "utf-8"))

    try:
        print(f"  📧 Conectando ao Gmail SMTP...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario, msg.as_string())

        print(f"  ✅ Email enviado para {destinatario}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("  ❌ Erro de autenticação — verifique a senha de app do Gmail.")
        print("     Gere em: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"  ❌ Erro ao enviar email: {e}")
        return False


# ─────────────────────────────────────────
# AGUARDAR RESPOSTA (IMAP)
# ─────────────────────────────────────────

def verificar_resposta(credenciais: dict, timeout_horas: int = 24) -> Optional[list[int]]:
    """
    Verifica a caixa de entrada por uma resposta "APLICAR" ou "APLICAR 1,3".
    Retorna lista de índices aprovados, ou None se não houver resposta ainda.
    Roda em loop com intervalo de 5 minutos.
    """
    remetente = credenciais["email_remetente"]
    senha = credenciais["senha_app"]
    deadline = datetime.now() + timedelta(hours=timeout_horas)

    print(f"\n⏳ Aguardando sua resposta por até {timeout_horas}h...")

    while datetime.now() < deadline:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(remetente, senha)
            mail.select("inbox")

            # Busca emails não lidos dos últimos 10 minutos
            data_busca = (datetime.now() - timedelta(minutes=10)).strftime("%d-%b-%Y")
            _, msgs = mail.search(None, f'(UNSEEN SINCE "{data_busca}" SUBJECT "Re:")')

            for num in msgs[0].split():
                _, data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                corpo = ""

                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            corpo = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                else:
                    corpo = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                corpo = corpo.strip().upper().split("\n")[0]  # primeira linha

                if "PAUSAR" in corpo:
                    print("  ⏸️  Comando PAUSAR recebido.")
                    mail.logout()
                    return []

                if "APLICAR" in corpo:
                    mail.logout()
                    # Verifica se há índices específicos
                    partes = corpo.replace("APLICAR", "").strip()
                    if partes:
                        try:
                            indices = [int(x.strip()) for x in partes.split(",")]
                            print(f"  ✅ Aprovação parcial recebida: vagas {indices}")
                            return indices
                        except ValueError:
                            pass
                    print("  ✅ Aprovação total recebida — aplicar em todas as vagas.")
                    return None  # None = todas

            mail.logout()

        except Exception as e:
            print(f"  ⚠️  Erro ao verificar email: {e}")

        print(f"  🔄 Sem resposta ainda. Verificando novamente em 5 minutos...")
        time.sleep(300)  # 5 minutos

    print("  ⏰ Timeout — nenhuma resposta recebida.")
    return []


# ─────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────

def notificar(vagas: list[dict], config: dict, credenciais: dict, aguardar: bool = True) -> list[dict]:
    """
    1. Envia o email com as vagas aprovadas
    2. Aguarda resposta (se notificar_antes=True)
    3. Retorna lista final de vagas para aplicar
    """
    if not vagas:
        print("  ℹ️  Nenhuma vaga para notificar.")
        return []

    print(f"\n📧 Módulo 4 — Notificação")
    print(f"   Vagas aprovadas para envio: {len(vagas)}")

    # Enviar email
    sucesso = enviar_email(vagas, config, credenciais)
    if not sucesso:
        print("  ⚠️  Email não enviado. Prosseguindo sem notificação.")
        if config.get("auto_aplicar"):
            return vagas  # auto-aplica mesmo sem email
        return []

    # Se auto_aplicar está ativo e não precisa de aprovação manual
    if config.get("auto_aplicar") and not config.get("notificar_antes"):
        print("  🚀 Modo auto-aplicar: prosseguindo sem aguardar aprovação.")
        return vagas

    if not aguardar:
        return []

    # Aguarda resposta
    resposta = verificar_resposta(credenciais)

    if resposta == []:  # timeout ou PAUSAR
        print("  ⏹️  Sem vagas para aplicar.")
        return []

    if resposta is None:  # APLICAR todas
        return vagas

    # APLICAR índices específicos (1-based)
    selecionadas = []
    for idx in resposta:
        if 1 <= idx <= len(vagas):
            selecionadas.append(vagas[idx - 1])
    print(f"  ✅ {len(selecionadas)} vaga(s) selecionadas para aplicação.")
    return selecionadas


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

def main():
    try:
        with open("config.json", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json não encontrado.")
        return

    try:
        with open("vagas_aprovadas.json", encoding="utf-8") as f:
            dados = json.load(f)
            vagas = dados.get("aprovadas", dados) if isinstance(dados, dict) else dados
    except FileNotFoundError:
        print("❌ vagas_aprovadas.json não encontrado. Rode o Módulo 3 primeiro.")
        return

    credenciais = carregar_credenciais()

    vagas_para_aplicar = notificar(vagas, config, credenciais, aguardar=True)

    # Salva para o Módulo 5
    with open("vagas_para_aplicar.json", "w", encoding="utf-8") as f:
        json.dump(vagas_para_aplicar, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Salvo em vagas_para_aplicar.json → próximo: Módulo 5 (Aplicador)")


if __name__ == "__main__":
    main()
