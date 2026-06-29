#!/usr/bin/env python3
import os, re, imaplib, email, html
from email.header import decode_header
from hermes_tools import send_message

ACCOUNT = os.environ.get("COM4_EMAIL_ACCOUNT", "")
PASSWORD = os.environ.get("COM4_EMAIL_PASSWORD", "")
IMAP_HOST = os.environ.get("COM4_EMAIL_IMAP_HOST", "")
IMAP_PORT = int(os.environ.get("COM4_EMAIL_IMAP_PORT", "993"))
TARGET_HEADER = "X-BeenThere"
TARGET_VALUE = "atendimento@com4.com.br"
STATE_FILE = os.path.expanduser("~/.hermes/state/com4_email_last_uid.txt")
STATE_DIR = os.path.dirname(STATE_FILE)
os.makedirs(STATE_DIR, exist_ok=True)

SKIP_SENDERS = [
    "notion", "tchaumilhas", "fibermarket", "techman",
    "gateway de spam", "mail delivery", "netcraft",
    "veroempresas", "moraisconsultoria", "vendas5@lacrefix.com",
    "sarah.dacu965@terra.com.br", "info@buscadedescontos.com",
    "gabriel.muquiriba.com", "rrexawet@yahoo.co.jp", "sale2@qmpowergen.com",
    "daniel@hcrway.com", "florence.acrylic@sedalong.com", "informativos@cra-rj.adm.br",
    "alsumood@emirates.net.ae",
]

KNOWN_ATTENDANTS = [
    "Alice Costa",
    "Bruno Lima",
    "Carlos Mendes",
    "Diana Souza",
    "Eduardo Faria",
    "Fernanda Rocha",
    "Gustavo Pinto",
    "Helena Dias",
    "Igor Santos",
    "Julia Martins",
]


def decode_text(raw):
    if raw is None:
        return ""
    parts = decode_header(raw)
    out = []
    for part, charset in parts:
        if isinstance(part, bytes):
            out.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out)


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text)


def first_lines(text: str, n: int = 2):
    clean = re.sub(r"\s+", " ", html.unescape(strip_html(text))).strip()
    if not clean:
        return "(sem conteúdo)"
    parts = [p.strip() for p in clean.replace("\r", "\n").split("\n") if p.strip()]
    lines = parts[:n]
    return " | ".join(lines)


def load_last_uid():
    try:
        with open(STATE_FILE, "r") as f:
            val = f.read().strip()
            return int(val) if val else 0
    except Exception:
        return 0


def save_last_uid(uid: int):
    with open(STATE_FILE, "w") as f:
        f.write(str(uid))


def main():
    if not IMAP_HOST:
        raise SystemExit("Defina COM4_EMAIL_IMAP_HOST no ambiente.")
    if not PASSWORD:
        raise SystemExit("Defina COM4_EMAIL_PASSWORD no ambiente.")

    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(ACCOUNT, PASSWORD)
    conn.select("INBOX")

    last_uid = load_last_uid()

    s, data = conn.uid("SEARCH", f"UID {last_uid + 1}:*")
    if s != "OK":
        conn.logout()
        raise SystemExit("Falha na busca IMAP")

    uids = data[0].split() if data and data[0] else []
    if not uids:
        conn.logout()
        return

    notifications = []
    new_max_uid = last_uid

    for uid in uids:
        uid_int = int(uid)
        if uid_int <= last_uid:
            continue
        new_max_uid = max(new_max_uid, uid_int)

        res, msg_data = conn.uid("FETCH", uid, "(RFC822)")
        if res != "OK" or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        header_value = decode_text(msg.get(TARGET_HEADER, ""))
        if header_value.lower() != TARGET_VALUE.lower():
            continue

        sender = decode_text(msg.get("From", ""))
        subject = decode_text(msg.get("Subject", "(sem assunto)"))
        if any(s in sender.lower() for s in SKIP_SENDERS):
            continue
        if "teste" in subject.lower():
            continue

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    if isinstance(payload, bytes):
                        body += payload.decode(charset, errors="replace")
                    else:
                        body += payload or ""
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            if isinstance(payload, bytes):
                body += payload.decode(charset, errors="replace")
            else:
                body += payload or ""

        summary = first_lines(body, 2)

        attendant_found = None
        for name in KNOWN_ATTENDANTS:
            if name.lower() in (body or "").lower():
                attendant_found = name
                break

        if attendant_found:
            notifications.append(
                f"Novo email atendimento\nRemetente: {sender}\nAssunto: {subject}\nResumo: {summary}\nAtendido por: {attendant_found}"
            )
        else:
            notifications.append(
                f"Novo email atendimento\nRemetente: {sender}\nAssunto: {subject}\nResumo: {summary}"
            )

    conn.logout()

    if notifications:
        save_last_uid(new_max_uid)
        text = "\n\n".join(notifications)
        send_message(target="whatsapp", message=text)
    else:
        save_last_uid(new_max_uid)


if __name__ == "__main__":
    main()
