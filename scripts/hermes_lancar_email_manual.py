#!/usr/bin/env python3
import sys, os, imaplib, email, socket, re
sys.path.insert(0, os.path.expanduser("~/.hermes/scripts"))
from com4_email_sheets import (
    get_sheets_service, get_current_sheet_name, ensure_sheet_exists,
    sheet_append, sheet_find_and_update, get_body_html, extract_attendant,
    get_sender_display, decode_str, parse_date, is_system_sender,
    IMAP_HOST, IMAP_PORT, ACCOUNT, PASSWORD,
    SKIP_SENDERS, KNOWN_ATTENDANTS
)

SKIP_SUBJECTS = ["teste","testes","testando","test","testing","trial","debug","e-mail teste","email teste","tst"]

def main():
    if len(sys.argv) < 2:
        print("USO: python hermes_lancar_email_manual.py <UID>")
        sys.exit(1)
    uid = sys.argv[1].strip().encode()
    socket.setdefaulttimeout(30)
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(ACCOUNT, PASSWORD)
    conn.select("INBOX")
    s, raw = conn.uid("FETCH", uid, "(RFC822)")
    conn.logout()
    if s != "OK" or not raw or not raw[0] or not isinstance(raw[0][1], bytes):
        print("[ERRO] Email nao encontrado.")
        sys.exit(1)
    msg = email.message_from_bytes(raw[0][1])
    from_hdr = decode_str(msg.get("From", ""))
    subject = decode_str(msg.get("Subject", "(sem assunto)"))
    msg_id = msg.get("Message-ID", "").strip()
    in_reply = " ".join(msg.get("In-Reply-To", "").split()).strip()
    date_hdr = msg.get("Date", "")
    html_body = get_body_html(msg)
    subject_lower = subject.lower()
    from_email = email.utils.parseaddr(from_hdr)[1].lower()
    is_skip_sender = any(s in from_email for s in SKIP_SENDERS)
    sender_display = get_sender_display(msg, from_hdr)
    received_at = parse_date(date_hdr)
    service = get_sheets_service()
    sheet_name = get_current_sheet_name()
    sheet_id = ensure_sheet_exists(service, sheet_name)
    is_reply_from_attendant = (in_reply and from_email == "atendimento@com4.com.br" and not is_skip_sender and "@com4.com.br" not in in_reply.lower())
    is_reply_from_client = (in_reply and "atendimento@com4.com.br" not in from_hdr.lower() and not is_skip_sender and not from_email.endswith("@com4.com.br"))
    if is_reply_from_attendant:
        attendant = extract_attendant(html_body)
        updated = sheet_find_and_update(service, sheet_name, sheet_id, in_reply, attendant, received_at)
        print(f"[OK] Respondido por {attendant}" if updated else f"[AVISO] Original nao encontrado: {in_reply}")
        return
    if is_reply_from_client:
        matched_attendant = next((n for n in KNOWN_ATTENDANTS if n.lower() in (html_body or "").lower()), None)
        if not matched_attendant and is_system_sender(sender_display, from_email):
            matched_attendant = "nao identificado"
        attendant_text = matched_attendant or "nao identificado"
        status_text = "Aguardando retorno do atendente"
        updated = sheet_find_and_update(service, sheet_name, sheet_id, in_reply, attendant_text, received_at, only_if_pending=True, status_label=status_text)
        if not updated:
            sheet_append(service, sheet_name, sheet_id, [sys.argv[1], msg_id, subject, sender_display, received_at, status_text, attendant_text, received_at])
        print(f"[OK] {status_text} — {sender_display}")
        return
    sheet_append(service, sheet_name, sheet_id, [sys.argv[1], msg_id, subject, sender_display, received_at, "Pendente", "", ""])
    print(f"[OK] Pendente — {sender_display} | {subject}")

if __name__ == "__main__":
    main()
