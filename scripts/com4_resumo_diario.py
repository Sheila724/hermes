#!/usr/bin/env python3
import json, os, socket, time, urllib.request, urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SPREADSHEET_ID   = os.environ.get("SHEETS_ID", "")
TOKEN_FILE       = os.path.expanduser("~/.hermes/google-token.json")

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

def get_current_sheet_name():
    now = datetime.now(BRASILIA_TZ)
    return f"Emails_{MESES_PT[now.month]}_{now.year}"

# WhatsApp: enviamos direto para a bridge local do Hermes (Baileys), em vez
# de usar o Telegram. WHATSAPP_GROUP_JID e o ID do grupo no formato
# "<numero>@g.us".
WHATSAPP_BRIDGE_PORT = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "3000"))
WHATSAPP_GROUP_JID   = os.environ.get("WHATSAPP_GROUP_JID", "")

# Timeout de rede global (em segundos) para evitar que o script trave
# indefinidamente em chamadas de API (Google Sheets / WhatsApp) e acabe
# sendo matado pelo timeout do cron sem nenhuma mensagem de erro.
socket.setdefaulttimeout(30)

MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos entre tentativas


def get_sheets_service():
    with open(TOKEN_FILE) as f:
        td = json.load(f)
    creds = Credentials(
        token=td['token'], refresh_token=td['refresh_token'],
        token_uri=td['token_uri'], client_id=td['client_id'],
        client_secret=td['client_secret'], scopes=td['scopes']
    )
    if creds.expired:
        creds.refresh(Request())
        td['token'] = creds.token
        with open(TOKEN_FILE, 'w') as f:
            json.dump(td, f)
    return build('sheets', 'v4', credentials=creds)


def fetch_rows_with_retry():
    """Busca as linhas da aba do mes atual, com retries em caso de erro de rede/API."""
    last_error = None
    sheet_name = get_current_sheet_name()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            service = get_sheets_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'{sheet_name}'!A:H"
            ).execute()
            return result.get('values', [])[1:]  # ignora cabecalho
        except Exception as e:
            last_error = e
            print(f"[AVISO] Tentativa {attempt}/{MAX_RETRIES} falhou ao ler a planilha (aba {sheet_name}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"Falha ao ler planilha (aba {sheet_name}) apos {MAX_RETRIES} tentativas: {last_error}")


def send_whatsapp(message, chat_id=None):
    """Envia mensagem via bridge local do WhatsApp (Baileys).
    Usa o endpoint HTTP da bridge diretamente (POST /send), em vez do
    'hermes send' CLI, porque o parser de target do CLI ainda nao reconhece
    corretamente JIDs de grupo (algo@g.us) no formato esperado.
    """
    target = chat_id or WHATSAPP_GROUP_JID
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            url = f"http://127.0.0.1:{WHATSAPP_BRIDGE_PORT}/send"
            payload = json.dumps({"chatId": target, "message": message}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("success"):
                    return
                raise RuntimeError(f"Bridge respondeu sem sucesso: {body}")
        except Exception as e:
            last_error = e
            print(f"[AVISO] Tentativa {attempt}/{MAX_RETRIES} falhou ao enviar WhatsApp: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"Falha ao enviar WhatsApp apos {MAX_RETRIES} tentativas: {last_error}")


def main():
    try:
        rows = fetch_rows_with_retry()
    except Exception as e:
        # Mesmo se a planilha falhar, avisa no WhatsApp em vez de ficar em silencio
        print(f"[ERRO] {e}")
        try:
            send_whatsapp(f"⚠️ Resumo do dia falhou ao ler a planilha:\n{e}")
        except Exception:
            pass
        return

    hoje = datetime.now(BRASILIA_TZ).strftime("%d/%m/%Y")
    total_hoje = 0
    respondidos_hoje = 0
    aguardando_atendente_hoje = 0
    spam_hoje = 0
    pendentes = []
    atendentes = {}

    for row in rows:
        if len(row) < 6:
            continue
        recebido = row[4] if len(row) > 4 else ""
        status   = row[5] if len(row) > 5 else ""
        assunto  = row[2] if len(row) > 2 else ""
        atendente = row[6] if len(row) > 6 else ""
        remetente = (row[3] if len(row) > 3 else "").lower()

        if any(tag in remetente for tag in ["gateway de spam", "mailer-daemon", "mail delivery", "email-gateway"]):
            continue

        if recebido.startswith(hoje):
            total_hoje += 1
            is_resposta_cliente = (
                status.startswith("Cliente respondeu")
                or atendente.startswith("Cliente:")
            )
            if is_resposta_cliente:
                aguardando_atendente_hoje += 1
            elif status.strip().lower() == "respondido":
                respondidos_hoje += 1
                if atendente and atendente != "Desconhecido":
                    atendentes[atendente] = atendentes.get(atendente, 0) + 1
            elif status.strip().lower() == "spam":
                spam_hoje += 1
            else:
                pendentes.append(assunto)

    pendentes_hoje = total_hoje - respondidos_hoje - aguardando_atendente_hoje - spam_hoje

    ranking = ""
    if atendentes:
        ordenado = sorted(atendentes.items(), key=lambda x: x[1], reverse=True)
        ranking = "\n🏆 Atendimentos por pessoa:\n"
        for nome, qtd in ordenado:
            ranking += f"  • {nome}: {qtd}\n"

    lista_pendentes = ""
    if pendentes:
        lista_pendentes = "\n⚠️ Ainda pendentes:\n"
        for p in pendentes[:5]:
            lista_pendentes += f"  • {p}\n"
        if len(pendentes) > 5:
            lista_pendentes += f"  • ... e mais {len(pendentes) - 5}\n"

    mensagem = (
        f"📊 Resumo do dia - {hoje}\n"
        f"{'='*30}\n"
        f"📨 Emails recebidos: {total_hoje}\n"
        f"✅ Respondidos: {respondidos_hoje}\n"
        f"🟡 Aguardando atendente: {aguardando_atendente_hoje}\n"
        f"🚫 Spam: {spam_hoje}\n"
        f"🔴 Pendentes: {pendentes_hoje}\n"
        f"{ranking}"
        f"{lista_pendentes}"
    )

    try:
        send_whatsapp(mensagem)
        print("Resumo enviado!")
    except Exception as e:
        print(f"[ERRO] Nao foi possivel enviar o resumo: {e}")


if __name__ == "__main__":
    main()
