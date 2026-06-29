import os, json, smtplib, ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from render_html_com4 import render_html

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

ACCOUNT   = os.environ.get("COM4_EMAIL_ACCOUNT", "")
SMTP_HOST = os.environ.get("COM4_EMAIL_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("COM4_EMAIL_SMTP_PORT", "587"))

_raw_pw = os.environ.get("COM4_EMAIL_PASSWORD", "")
if not _raw_pw:
    try:
        with open(os.path.expanduser("~/.hermes/config.yaml"), "rb") as f:
            for line in f.read().decode("utf-8", errors="ignore").splitlines():
                _line = line.strip()
                if _line.startswith("COM4_EMAIL_PASSWORD:"):
                    _raw_pw = _line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
PASSWORD = _raw_pw

DESTINATARIOS = os.environ.get(
    "RELATORIO_DESTINATARIOS",
    "gestao@example.com"
).split(",")

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro",10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

MESES_PT_DISPLAY = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro",10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

COLUNAS = ["UID", "Message-ID", "Assunto", "Remetente", "Recebido", "Status", "Atendente", "Respondido Em"]

SPREADSHEET_ID = os.environ.get("SHEETS_ID", "")
TOKEN_FILE     = os.path.expanduser("~/.hermes/google-token.json")


def _get_sheet_name():
    now = datetime.now(BRASILIA_TZ)
    return f"Emails_{MESES_PT[now.month]}_{now.year}"


def _get_sheets_service():
    with open(TOKEN_FILE) as f:
        td = json.load(f)
    creds = Credentials(
        token=td["token"],
        refresh_token=td["refresh_token"],
        token_uri=td["token_uri"],
        client_id=td["client_id"],
        client_secret=td["client_secret"],
        scopes=td["scopes"],
    )
    if creds.expired:
        creds.refresh(Request())
        td["token"] = creds.token
        with open(TOKEN_FILE, "w") as f:
            json.dump(td, f)
    return build("sheets", "v4", credentials=creds)


def carregar_linhas_csv():
    service = _get_sheets_service()
    sheet_name = _get_sheet_name()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"'{sheet_name}'!A:H")
        .execute()
    )
    valores = result.get("values", [])[1:]
    linhas = []
    for r in valores:
        if not any(v.strip() for v in r):
            continue
        linha = {COLUNAS[i]: (r[i].strip() if i < len(r) else "") for i in range(len(COLUNAS))}
        linhas.append(linha)
    return linhas


def parse_recebido(linha):
    valor = (linha.get("Recebido") or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            pass
    return None


def filtrar_periodo(linhas, data_inicio, data_fim):
    selecionadas = []
    for linha in linhas:
        recebido = parse_recebido(linha)
        if recebido and data_inicio <= recebido <= data_fim:
            selecionadas.append(linha)
    return selecionadas


def email_considerado(linha):
    status   = (linha.get("Status")   or "").strip().lower()
    atendente = (linha.get("Atendente") or "").strip().lower()
    return status != "spam" and atendente != "spam"


def construir_report(linhas, periodo_label, data_inicio, data_fim):
    considerados = [linha for linha in linhas if email_considerado(linha)]

    respondidos_linhas = [
        linha for linha in considerados
        if (linha.get("Status") or "").strip().lower().startswith("respondido")
    ]

    aguardando_linhas = [
        linha for linha in considerados
        if (linha.get("Status") or "").strip().lower().replace("_", " ") == "aguardando retorno do atendente"
        or (linha.get("Atendente") or "").strip().lower() == "aguardando retorno do atendente"
    ]

    normalizado_linhas = [
        linha for linha in considerados
        if (linha.get("Status") or "").strip().lower().startswith("normalizado")
    ]

    por_atendente = {}
    for linha in respondidos_linhas:
        atendente = (linha.get("Atendente") or "").strip()
        if not atendente:
            continue
        por_atendente[atendente] = por_atendente.get(atendente, 0) + 1

    total_emails        = len(considerados)
    respondidos         = len(respondidos_linhas)
    aguardando_atendente = len(aguardando_linhas)
    normalizado         = len(normalizado_linhas)
    pendentes           = total_emails - respondidos - aguardando_atendente - normalizado

    return {
        "periodo_label":       periodo_label,
        "data_inicio":         data_inicio,
        "data_fim":            data_fim,
        "total_emails":        total_emails,
        "respondidos":         respondidos,
        "pendentes":           pendentes,
        "aguardando_atendente": aguardando_atendente,
        "normalizado":         normalizado,
        "por_atendente":       por_atendente,
    }


def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = ACCOUNT
    msg["To"]      = ", ".join(DESTINATARIOS)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls(context=context)
        server.login(ACCOUNT, PASSWORD)
        server.sendmail(ACCOUNT, DESTINATARIOS, msg.as_string())


def main():
    import sys
    tipo = sys.argv[1] if len(sys.argv) > 1 else "semanal"

    agora = datetime.now(BRASILIA_TZ).replace(tzinfo=None)

    if tipo == "semanal":
        dias_desde_segunda = agora.weekday()
        inicio_semana_atual = (agora - timedelta(days=dias_desde_segunda)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        data_fim    = inicio_semana_atual - timedelta(seconds=1)
        data_inicio = inicio_semana_atual - timedelta(days=7)
        periodo_label = "semanal"
        assunto = f"Relatorio semanal COM4 - {data_inicio.strftime('%d/%m')} a {data_fim.strftime('%d/%m/%Y')}"

    elif tipo == "diario":
        data_inicio   = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        data_fim      = agora
        periodo_label = "diario"
        assunto = f"Relatorio diario COM4 - {data_inicio.strftime('%d/%m/%Y')}"

    else:
        # Mes anterior completo
        primeiro_dia_mes_atual = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data_fim    = primeiro_dia_mes_atual - timedelta(seconds=1)
        data_inicio = data_fim.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        periodo_label = "mensal"
        assunto = f"Relatorio mensal COM4 - {MESES_PT_DISPLAY[data_inicio.month]}/{data_inicio.year}"

    linhas          = carregar_linhas_csv()
    linhas_filtradas = filtrar_periodo(linhas, data_inicio, data_fim)
    report          = construir_report(linhas_filtradas, periodo_label, data_inicio, data_fim)
    html_body       = render_html(report)

    send_email(assunto, html_body)
    print(f"Relatorio {periodo_label} enviado para: {', '.join(DESTINATARIOS)}")
    print(f"Periodo: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
    print(
        f"Emails: {report['total_emails']} | "
        f"Respondidos: {report['respondidos']} | "
        f"Pendentes: {report['pendentes']} | "
        f"Aguardando retorno: {report.get('aguardando_atendente', 0)} | "
        f"Normalizado: {report.get('normalizado', 0)}"
    )


if __name__ == "__main__":
    main()
