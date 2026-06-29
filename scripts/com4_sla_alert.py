#!/usr/bin/env python3
"""
Alerta de SLA - COM4 Hermes
Roda via cron job a cada 15 minutos. Verifica emails na aba do mês atual
e dispara alerta no WhatsApp nos seguintes casos:

  • Status "Pendente" → sem nenhuma resposta da equipe
  • Status "Aguardando retorno do atendente" → cliente respondeu mas a
    equipe ainda não voltou

Ambos os casos disparam após SLA_HORAS (padrão: 2h) e se repetem a cada
REPEAT_HORAS (padrão: 1h). Só envia alertas durante o horário comercial
(HORA_INICIO–HORA_FIM).
"""
import json, os, socket, time, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

SPREADSHEET_ID   = os.environ.get("SHEETS_ID", "")
TOKEN_FILE       = os.path.expanduser("~/.hermes/google-token.json")
STATE_FILE       = os.path.expanduser("~/.hermes/state/com4_sla_notified.json")
RESPONSAVEL_FILE = os.path.expanduser("~/.hermes/state/responsavel_semana.json")

os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

SLA_HORAS    = float(os.environ.get("SLA_HORAS",        "2"))
HORA_INICIO  = int(os.environ.get("SLA_HORA_INICIO",    "8"))
HORA_FIM     = int(os.environ.get("SLA_HORA_FIM",       "18"))
REPEAT_HORAS = float(os.environ.get("SLA_REPEAT_HORAS", "1"))

WHATSAPP_BRIDGE_PORT = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "3000"))
WHATSAPP_GROUP_JID   = os.environ.get("WHATSAPP_GROUP_JID", "")

socket.setdefaulttimeout(30)
MAX_RETRIES = 3
RETRY_DELAY = 5

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro",10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

STATUS_PENDENTE           = "pendente"
STATUS_AGUARDANDO_RETORNO = "aguardando retorno do atendente"


def get_current_sheet_name():
    now = datetime.now(BRASILIA_TZ)
    return f"Emails_{MESES_PT[now.month]}_{now.year}"


def get_sheets_service():
    with open(TOKEN_FILE) as f:
        td = json.load(f)
    creds = Credentials(
        token=td["token"], refresh_token=td["refresh_token"],
        token_uri=td["token_uri"], client_id=td["client_id"],
        client_secret=td["client_secret"], scopes=td["scopes"],
    )
    if creds.expired:
        creds.refresh(Request())
        td["token"] = creds.token
        with open(TOKEN_FILE, "w") as f:
            json.dump(td, f)
    return build("sheets", "v4", credentials=creds)


def fetch_rows_with_retry():
    last_error = None
    sheet_name = get_current_sheet_name()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            service = get_sheets_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'{sheet_name}'!A:H",
            ).execute()
            return result.get("values", [])[1:]
        except Exception as e:
            last_error = e
            print(f"[AVISO] Tentativa {attempt}/{MAX_RETRIES} falhou: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"Falha ao ler planilha apos {MAX_RETRIES} tentativas: {last_error}")


def send_whatsapp(message, chat_id=None):
    target = chat_id or WHATSAPP_GROUP_JID
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            url = f"http://127.0.0.1:{WHATSAPP_BRIDGE_PORT}/send"
            payload = json.dumps({"chatId": target, "message": message}).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("success"):
                    return
                raise RuntimeError(f"Bridge sem sucesso: {body}")
        except Exception as e:
            last_error = e
            print(f"[AVISO] Tentativa {attempt}/{MAX_RETRIES} falhou ao enviar WA: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"Falha ao enviar WhatsApp apos {MAX_RETRIES} tentativas: {last_error}")


def extrair_nome_cliente(from_hdr):
    from_hdr = (from_hdr or "").strip()
    if "<" in from_hdr:
        nome = from_hdr.split("<")[0].strip().strip('"')
        if nome:
            return nome
        # Sem nome de exibição — retorna o email completo
        email_addr = from_hdr.split("<")[1].split(">")[0].strip()
        return email_addr
    if "@" in from_hdr:
        return from_hdr.strip()
    return from_hdr or "Desconhecido"


def parse_recebido(recebido_str):
    try:
        return datetime.strptime(recebido_str.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=BRASILIA_TZ)
    except Exception:
        return None


def load_responsavel():
    try:
        with open(RESPONSAVEL_FILE) as f:
            data = json.load(f)
        nome = (data.get("responsavel") or "").strip()
        if nome:
            return f"*{nome}*"
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[AVISO] Falha ao ler responsavel: {e}")
    return "*Responsavel nao definido*"


def _load_notified():
    try:
        with open(STATE_FILE) as f:
            payload = json.load(f)
        data = payload.get("notified_message_ids", {})
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {msg_id: "1970-01-01T00:00:00" for msg_id in data}
        return {}
    except Exception:
        return {}


def _save_notified(notified_dict):
    with open(STATE_FILE, "w") as f:
        json.dump({"notified_message_ids": notified_dict}, f)


def formatar_horas(horas):
    h = int(horas)
    m = int((horas - h) * 60)
    if h > 0 and m > 0:
        return f"{h}h{m:02d}min"
    if h > 0:
        return f"{h}h"
    return f"{m}min"


def montar_mensagem_pendente(item, responsavel):
    tempo = formatar_horas(item["horas"])
    return (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "\u23f0 *SLA \u2014 Sem resposta*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f464 Cliente: {item['cliente']}\n"
        f"\U0001f4cb Assunto: {item['assunto']}\n"
        f"\U0001f550 Aguardando ha: *{tempo}*\n"
        f"\U0001f454 Responsavel: {responsavel}"
    )


def montar_mensagem_aguardando_retorno(item):
    tempo = formatar_horas(item["horas"])
    atendente = item.get("atendente", "").strip()
    sem_nome = atendente.lower() in ("", "nao identificado", "desconhecido", "cliente:")
    linha_atendente = (
        f"\U0001f454 Atendente: *{atendente}*\n"
        if not sem_nome
        else ""
    )
    return (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "\U0001f4ac *Cliente aguardando retorno*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f464 Cliente: {item['cliente']}\n"
        f"\U0001f4cb Assunto: {item['assunto']}\n"
        f"\U0001f550 Aguardando ha: *{tempo}*\n"
        f"{linha_atendente}"
        "\U0001f4e5 Respondeu e aguarda retorno da equipe"
    )


def main():
    agora = datetime.now(BRASILIA_TZ)

    if not (HORA_INICIO <= agora.hour < HORA_FIM):
        print(f"[INFO] Fora do horario comercial ({HORA_INICIO}h-{HORA_FIM}h).")
        return

    try:
        rows = fetch_rows_with_retry()
    except Exception as e:
        print(f"[ERRO] {e}")
        return

    alertas = []
    for row in rows:
        if len(row) < 6:
            continue
        msg_id    = row[1] if len(row) > 1 else ""
        assunto   = row[2] if len(row) > 2 else ""
        from_hdr  = row[3] if len(row) > 3 else ""
        recebido  = row[4] if len(row) > 4 else ""
        status    = (row[5] if len(row) > 5 else "").strip().lower()
        atendente = (row[6] if len(row) > 6 else "").strip()

        if status not in (STATUS_PENDENTE, STATUS_AGUARDANDO_RETORNO):
            continue
        if not msg_id:
            continue

        # Para "aguardando retorno", conta a partir de quando o cliente respondeu
        # (coluna H = Respondido Em), com fallback para Recebido
        if status == STATUS_AGUARDANDO_RETORNO:
            respondido_em = (row[7] if len(row) > 7 else "").strip()
            base_dt = parse_recebido(respondido_em) or parse_recebido(recebido)
        else:
            base_dt = parse_recebido(recebido)

        if not base_dt:
            continue

        horas_pendente = (agora - base_dt).total_seconds() / 3600
        if horas_pendente >= SLA_HORAS:
            alertas.append({
                "msg_id":    msg_id,
                "cliente":   extrair_nome_cliente(from_hdr),
                "assunto":   assunto,
                "horas":     horas_pendente,
                "status":    status,
                "atendente": atendente,
            })

    if not alertas:
        print("[INFO] Nenhum email acima do SLA.")
        return

    notified    = _load_notified()
    houve_alter = False
    responsavel = load_responsavel()

    for item in alertas:
        last_str = notified.get(item["msg_id"])
        if last_str:
            try:
                last_dt = datetime.fromisoformat(last_str)
                if (agora - last_dt).total_seconds() / 3600 < REPEAT_HORAS:
                    continue
            except Exception:
                pass

        if item["status"] == STATUS_AGUARDANDO_RETORNO:
            mensagem = montar_mensagem_aguardando_retorno(item)
        else:
            mensagem = montar_mensagem_pendente(item, responsavel)

        try:
            send_whatsapp(mensagem)
            print(f"[ALERTA] {item['status'].upper()} | {item['cliente']} | {formatar_horas(item['horas'])}")
            notified[item["msg_id"]] = agora.isoformat()
            houve_alter = True
        except Exception as e:
            print(f"[ERRO] Nao enviou alerta para {item['cliente']}: {e}")

    # Remove do estado msg_ids que nao estao mais em alerta
    msg_ids_em_alerta = {a["msg_id"] for a in alertas}
    para_remover = set(notified.keys()) - msg_ids_em_alerta
    if para_remover:
        for msg_id in para_remover:
            del notified[msg_id]
        houve_alter = True

    if houve_alter:
        try:
            _save_notified(notified)
        except Exception as e:
            print(f"[ERRO] Nao salvou estado do SLA: {e}")


if __name__ == "__main__":
    main()
