#!/usr/bin/env python3
import os
import re
import imaplib
import email
import socket
import json
import urllib.request
from email.header import decode_header
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from com4_email_sheets import get_sheets_service, get_current_sheet_name, SPREADSHEET_ID

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")


def format_date_br(date_hdr):
    try:
        dt = parsedate_to_datetime(date_hdr)
        dt = dt.astimezone(BRASILIA_TZ)
        return dt.strftime("%d/%m/%Y as %Hh%M")
    except Exception:
        return ""


ACCOUNT  = os.environ.get("COM4_EMAIL_ACCOUNT", "")
PASSWORD = os.environ.get("COM4_EMAIL_PASSWORD", "")
IMAP_HOST = os.environ.get("COM4_EMAIL_IMAP_HOST", "")
IMAP_PORT = int(os.environ.get("COM4_EMAIL_IMAP_PORT", "993"))

WHATSAPP_BRIDGE_PORT = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "3000"))
WHATSAPP_GROUP_JID   = os.environ.get("WHATSAPP_GROUP_JID", "")

RESPONSAVEIS = {}

STATE_FILE      = os.path.expanduser("~/.hermes/state/com4_email_last_uid.txt")
ATT_REPLY_STATE = os.path.expanduser("~/.hermes/state/com4_attendant_replied_notified.json")
BLOCKED_SENDERS_FILE = os.path.expanduser("~/.hermes/state/com4_blocked_senders.json")

MAX_EMAILS_PER_RUN = 20
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
os.makedirs(os.path.dirname(ATT_REPLY_STATE), exist_ok=True)
os.makedirs(os.path.dirname(BLOCKED_SENDERS_FILE), exist_ok=True)

SKIP_SENDERS = [
    "notion", "tchaumilhas", "fibermarket", "techman", "mailer-daemon",
    "gateway de spam", "mail delivery", "pagamento@", "contabilidade",
    "cartorio", "mercado livre", "vendas5@lacrefix.com",
    "sarah.dacu965@terra.com.br", "info@buscadedescontos.com",
    "gabriel.muquiriba.com", "rrexawet@yahoo.co.jp", "sale2@qmpowergen.com",
    "daniel@hcrway.com", "florence.acrylic@sedalong.com",
    "informativos@cra-rj.adm.br", "albert@deqiaote.com",
    "lucas@softecho-art.com", "cartaodetodos.com",
    "5338832t.cartaodetodos.com", "aejmyfxex@yahoo.co.jp",
    "mpa@mpainformatica.com", "hostmaster@registro.br",
    "xhdjzrkplzkd@gmail.com", "brian@exportimportexchange.com",
    "janice@abiscircuits.cn", "schen@huayanpet.com",
    "dflirge@gmail.com", "compta.fournisseurs@sosaca.fr",
]
SILENT_SKIP_SENDERS = [
    "mailer-daemon", "postmaster@email-gateway", "mail delivery"
]
SKIP_SUBJECTS = [
    "teste", "test", "testing", "e-mail teste", "email teste",
    "verificacao", "verificando", "check", "ping", "disinfected", "tst",
    "recebido",
]
PALAVRAS_URGENTES = [
    "urgente", "sem internet", "fora do ar", "caiu", "nao conecta",
    "sem conexao", "bloqueado", "suspenso", "cancelar", "juridico",
    "advogado", "procon", "reclame aqui",
]
PROTOCOLO_MARKERS = ["registrado com sucesso", "seu atendimento foi registrado"]


def load_blocked_senders():
    try:
        with open(BLOCKED_SENDERS_FILE) as f:
            return set(json.load(f).get("blocked", []))
    except Exception:
        return set()


def decode_str(value):
    if not value:
        return ""
    parts = decode_header(value)
    result = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += part
    return result


def load_last_uid():
    try:
        with open(STATE_FILE) as f:
            val = f.read().strip()
            return int(val) if val else 0
    except Exception:
        return 0


def save_last_uid(uid):
    with open(STATE_FILE, "w") as f:
        f.write(str(uid))


def get_max_uid(conn):
    s, data = conn.uid("SEARCH", "ALL")
    if s == "OK" and data and data[0]:
        uids = data[0].split()
        if uids:
            return int(uids[-1])
    return 0


def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body += payload.decode(charset, errors="replace")
    body = re.sub(r"<[^>]+>", " ", body)
    lines = [l.strip() for l in body.replace("\r", "\n").split("\n") if l.strip() and len(l.strip()) > 5]
    return " | ".join(lines[:2]) if lines else "(sem conteudo)"


def get_body_html(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return ""


def extract_attendant(html):
    def clean_name(raw):
        cleaned = re.sub(r"<[^>]+>", " ", raw)
        cleaned = re.sub(r"&[a-z]+;", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    full = html or ""

    try:
        match = re.search(
            r"color:\s*#FF9900[^>]*>(.{2,300}?)(?:</span>|</b>|</p>|</div>|</td>)",
            full, re.IGNORECASE | re.DOTALL
        )
        if match:
            name = clean_name(match.group(1))
            if 3 <= len(name) <= 80 and "\n" not in name and "@" not in name:
                return name
    except Exception:
        pass

    extra_names = [
        "Alice Costa", "Bruno Lima", "Carlos Mendes", "Diana Souza",
        "Eduardo Faria", "Fernanda Rocha", "Gustavo Pinto",
        "Helena Dias", "Igor Santos", "Julia Martins",
    ]
    low = full.lower()
    for name in extra_names:
        if name.lower() in low:
            return name
    return "Atendente"


def safe_imap_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, int):
        return str(value).encode("utf-8")
    if isinstance(value, str):
        return value.encode("utf-8")
    return b""


def is_urgente(subject, body):
    texto = (subject + " " + body).lower()
    return any(p in texto for p in PALAVRAS_URGENTES)


def find_responsavel(subject, body):
    texto = (subject + " " + body).lower()
    for palavra, numero in RESPONSAVEIS.items():
        if palavra.lower() in texto:
            return numero
    return None


def send_whatsapp(message, mention_number=None):
    target = WHATSAPP_GROUP_JID
    full_message = message
    if mention_number:
        full_message = f"@{mention_number} {message}"
    url = f"http://127.0.0.1:{WHATSAPP_BRIDGE_PORT}/send"
    payload = json.dumps({"chatId": target, "message": full_message}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        if not body.get("success"):
            raise RuntimeError(f"Bridge respondeu sem sucesso: {body}")


def extract_email_from_header(header_line):
    import email.utils
    _, addr = email.utils.parseaddr(header_line)
    return addr.strip().lower()


def main():
    if not PASSWORD:
        raise SystemExit("Defina COM4_EMAIL_PASSWORD")

    dynamic_blocked = load_blocked_senders()

    socket.setdefaulttimeout(30)
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(ACCOUNT, PASSWORD)
    conn.select("INBOX")
    last_uid = load_last_uid()
    if last_uid == 0:
        max_uid = get_max_uid(conn)
        if max_uid > 0:
            save_last_uid(max_uid)
        conn.logout()
        return

    s, data = conn.uid("SEARCH", f"UID {last_uid + 1}:*")
    if s != "OK" or not data or not data[0]:
        conn.logout()
        return

    uids = data[0].split()
    if not uids:
        conn.logout()
        return

    uids = uids[:MAX_EMAILS_PER_RUN]
    new_max_uid = last_uid

    for uid in uids:
        uid_int = int(uid)
        if uid_int <= last_uid:
            continue

        try:
            s2, hdata = conn.uid("FETCH", uid, "(BODY.PEEK[HEADER])")
            if s2 != "OK" or not hdata or not hdata[0]:
                continue

            header_raw = safe_imap_bytes(hdata[0][1]).decode("utf-8", errors="replace")

            if "x-beenthere: atendimento@com4.com.br" not in header_raw.lower():
                new_max_uid = max(new_max_uid, uid_int)
                continue

            from_line = ""
            sender_hdr = ""
            for line in header_raw.splitlines():
                if line.lower().startswith("from:"):
                    from_line = line.strip()
                    sender_hdr = line
                    break

            from_email_quick = extract_email_from_header(sender_hdr or from_line)

            if any(s in from_email_quick for s in SILENT_SKIP_SENDERS):
                new_max_uid = max(new_max_uid, uid_int)
                continue

            if any(s in from_email_quick for s in SKIP_SENDERS) or from_email_quick in dynamic_blocked:
                new_max_uid = max(new_max_uid, uid_int)
                continue

            s3, mdata = conn.uid("FETCH", uid, "(RFC822)")
            if s3 != "OK" or not mdata or not mdata[0]:
                continue

            raw_msg = mdata[0][1]
            if not isinstance(raw_msg, bytes):
                new_max_uid = max(new_max_uid, uid_int)
                continue
            msg = email.message_from_bytes(raw_msg)

            in_reply = msg.get("In-Reply-To", "").strip()
            from_email = extract_email_from_header(msg.get("From", ""))

            sender = decode_str(msg.get("From", ""))
            subject = decode_str(msg.get("Subject", "(sem assunto)"))
            subject_lower = subject.lower()
            to_hdr = decode_str(msg.get("To", "")).lower()

            # Encaminhamento interno
            is_forward_interno = (
                from_email.endswith("@com4.com.br")
                and "@com4.com.br" in to_hdr
                and (
                    subject_lower.startswith("fw:")
                    or subject_lower.startswith("fwd:")
                    or subject_lower.startswith("enc:")
                )
                and not any(s in subject_lower for s in SKIP_SUBJECTS)
            )

            in_reply_is_external = bool(in_reply) and "@com4.com.br" not in in_reply.lower()
            is_reply_from_attendant = (
                in_reply_is_external
                and from_email == "atendimento@com4.com.br"
                and not is_forward_interno
            )
            is_reply_from_client = (
                bool(in_reply)
                and not is_reply_from_attendant
                and not is_forward_interno
                and not from_email.endswith("@com4.com.br")
            )

            # Email da equipe sem reply e sem encaminhamento interno -> ignora
            is_site_contact_form = (
                from_email == "contatosite@com4.com.br"
                and "com4 site - contato para você" in subject_lower
            )
            if (
                from_email.endswith("@com4.com.br")
                and not is_site_contact_form
                and not in_reply
                and not is_forward_interno
            ):
                new_max_uid = max(new_max_uid, uid_int)
                continue

            # Encaminhamento interno -> notifica grupo
            if is_forward_interno:
                html_fw = get_body_html(msg) or ""
                attendant = extract_attendant(html_fw)
                data_formatada = format_date_br(msg.get("Date", "")) or decode_str(msg.get("Date", ""))
                to_display = decode_str(msg.get("To", "")).strip()
                if attendant in ("Atendente", "", None):
                    import email.utils as _eu
                    _name, _addr = _eu.parseaddr(decode_str(msg.get("From", "")))
                    if _name:
                        attendant = _name
                forward_message = (
                    "📤 Encaminhado internamente\n"
                    f"Assunto: {subject}\n"
                    f"Para: {to_display}\n"
                    f"Por: _{attendant}_ em {data_formatada or '(sem data)'}"
                )
                try:
                    send_whatsapp(forward_message)
                except Exception as e:
                    print(f"Erro ao enviar WhatsApp (encaminhamento interno): {e}")
                new_max_uid = max(new_max_uid, uid_int)
                continue

            if is_reply_from_attendant and not any(s in subject_lower for s in SKIP_SUBJECTS):
                in_reply_id = decode_str(msg.get("In-Reply-To", "")).strip()

                notified_path = os.path.expanduser("~/.hermes/state/wa_responded_notified.json")
                notified = set()
                try:
                    with open(notified_path) as f:
                        notified = set(json.load(f).get("responded_uids", []))
                except Exception:
                    pass

                if str(uid_int) in notified:
                    new_max_uid = max(new_max_uid, uid_int)
                    continue

                attendant = extract_attendant(get_body_html(msg) or "")
                replied_at = format_date_br(msg.get("Date", "")) or decode_str(msg.get("Date", ""))

                # Busca dados do cliente original na planilha
                cliente_sender = ""
                cliente_subject = ""
                try:
                    service = get_sheets_service()
                    sheet_name = get_current_sheet_name()
                    result = service.spreadsheets().values().get(
                        spreadsheetId=SPREADSHEET_ID,
                        range=f"'{sheet_name}'!A:H",
                    ).execute()
                    rows = result.get("values", [])[1:]
                    in_reply_norm = in_reply_id.strip().strip("<>").lower()
                    for row in rows:
                        if len(row) > 3:
                            row_msgid = row[1].strip().strip("<>").lower()
                            if row_msgid == in_reply_norm:
                                cliente_sender = row[3]
                                cliente_subject = row[2]
                                break
                except Exception as e:
                    print(f"[AVISO] Nao buscou email original na planilha: {e}")

                if cliente_sender:
                    # Email original encontrado na planilha — notifica normalmente
                    response_message = (
                        "✅ Respondido\n"
                        f"Assunto: {cliente_subject or subject}\n"
                        f"Cliente: {cliente_sender}\n"
                        f"Por: _{attendant}_ em {replied_at or '(sem data)'}"
                    )
                    try:
                        send_whatsapp(response_message)
                        notified.add(str(uid_int))
                        with open(notified_path, "w") as f:
                            json.dump({"responded_uids": list(notified)}, f)
                    except Exception as e:
                        print(f"Erro ao enviar WhatsApp (resposta da equipe): {e}")
                else:
                    # Email original NÃO encontrado na planilha — foi um email
                    # de teste ou ignorado. Silencia a notificação.
                    print(f"[IGNORADO] Resposta sem email original na planilha: {subject}")
                    notified.add(str(uid_int))
                    with open(notified_path, "w") as f:
                        json.dump({"responded_uids": list(notified)}, f)

                new_max_uid = max(new_max_uid, uid_int)
                continue

            if is_reply_from_client and not any(s in subject_lower for s in SKIP_SUBJECTS):
                data_formatada = format_date_br(msg.get("Date", ""))
                rodape_data = f"\n\nEnviado dia {data_formatada}" if data_formatada else ""

                NORMALIZADO_MARKERS = [
                    "normalizado", "restabelecido", "voltou ao normal",
                    "resolvido", "encerrar ticket", "encerrar nosso ticket"
                ]
                corpo_check = get_body(msg).lower()
                is_normalizado = any(marker in corpo_check for marker in NORMALIZADO_MARKERS)

                if is_normalizado:
                    client_reply_message = (
                        "✅ Normalizado pelo cliente\n"
                        f"De: {sender}\n"
                        f"Assunto: {subject}\n"
                        f"Sem necessidade de ação da equipe"
                        f"{rodape_data}"
                    )
                else:
                    client_reply_message = (
                        "📧 Resposta de cliente\n"
                        f"De: {sender}\n"
                        f"Assunto: {subject}"
                        f"{rodape_data}"
                    )
                try:
                    send_whatsapp(client_reply_message)
                except Exception as e:
                    print(f"Erro ao enviar WhatsApp (resposta de cliente): {e}")
                new_max_uid = max(new_max_uid, uid_int)
                continue

            if any(s in subject_lower for s in SKIP_SUBJECTS):
                new_max_uid = max(new_max_uid, uid_int)
                continue

            body = get_body(msg)

            if any(marker in body.lower() for marker in PROTOCOLO_MARKERS):
                new_max_uid = max(new_max_uid, uid_int)
                continue

            responsavel = find_responsavel(subject, body)
            data_formatada = format_date_br(msg.get("Date", ""))
            rodape_data = f"\n\nEnviado dia {data_formatada}" if data_formatada else ""

            if is_urgente(subject, body):
                message = (
                    f"🚨 EMAIL URGENTE - Atendimento COM4 🚨\n\n"
                    f"De: {sender}\n"
                    f"Assunto: {subject}\n"
                    f"Resumo: {body}"
                    f"{rodape_data}"
                )
            else:
                message = (
                    f"📧 Novo email - Atendimento COM4\n\n"
                    f"De: {sender}\n"
                    f"Assunto: {subject}\n"
                    f"Resumo: {body}"
                    f"{rodape_data}"
                )
            try:
                send_whatsapp(message, mention_number=responsavel)
            except Exception as e:
                print(f"Erro ao enviar WhatsApp: {e}")
            new_max_uid = max(new_max_uid, uid_int)

        except Exception as e:
            print(f"[ERRO] UID {uid_int}: {e}")
            new_max_uid = max(new_max_uid, uid_int)
            continue

    if new_max_uid > last_uid:
        save_last_uid(new_max_uid)

    conn.logout()


if __name__ == "__main__":
    main()
