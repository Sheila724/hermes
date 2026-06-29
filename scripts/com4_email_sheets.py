import imaplib, email, os, re, json
import zoneinfo
from datetime import datetime
from email.header import decode_header
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────
IMAP_HOST      = os.environ.get("COM4_EMAIL_IMAP_HOST", "")
IMAP_PORT      = int(os.environ.get("COM4_EMAIL_IMAP_PORT", 993))
ACCOUNT        = os.environ.get("COM4_EMAIL_ACCOUNT", "")
PASSWORD       = os.environ.get("COM4_EMAIL_PASSWORD", "")
SPREADSHEET_ID = os.environ.get("SHEETS_ID", "")
TOKEN_FILE     = os.path.expanduser("~/.hermes/google-token.json")
UID_FILE       = os.path.expanduser("~/.hermes/com4_last_uid.txt")

SKIP_SENDERS = [
    "notion", "tchaumilhas", "fibermarket", "techman",
    "gateway de spam", "mail delivery", "netcraft",
    "veroempresas", "moraisconsultoria",
    "vendas5@lacrefix.com", "sarah.dacu965@terra.com.br",
    "info@buscadedescontos.com", "gabriel.muquiriba.com",
    "rrexawet@yahoo.co.jp", "sale2@qmpowergen.com",
    "daniel@hcrway.com", "florence.acrylic@sedalong.com",
    "informativos@cra-rj.adm.br", "alsumood@emirates.net.ae",
    "mailer-daemon", "joanne@gelaifurniture.com",
    "albert@deqiaote.com", "pontoisp@pontoisp.com.br",
    "wochang@wochangtrolley.com", "vivoservicos@ugwygwyjufgysdhyebe.store",
    "envio@envioeletrolar.com.br", "lara.kauane@allivmail.com.br",
    "vendas@advocacia.starley.com.br", "mpa@mpainformatica.com",
    "hostmaster@registro.br", "relacionamento@reclamecentral.store",
    "brian@exportimportexchange.com", "xhdjzrkplzkd@gmail.com",
    "janice@abiscircuits.cn", "schen@huayanpet.com",
    "cartaodetodos.com", "5338832t.cartaodetodos.com",
    "anesilva@superit.net.br", "dflirge@gmail.com",
    "fcmjoo@gmail.com", "compta.fournisseurs@sosaca.fr",
]

SKIP_SUBJECTS = [
    "teste", "testes", "testando", "test", "testing", "trial", "debug", " smoke ",
    "e-mail teste", "email teste", "assunto teste", "assunto: teste",
    "teste: ", "teste - ", "[teste]", "[test]", "teste final", "teste de envio",
    "falso", "fake", "simulado", "simulacao", "simulacao", "tst",
]

# Prefixos de spam do gateway que NÃO devem ser ignorados —
# o email pode ser legítimo mesmo com o prefixo SPAM: no assunto.
# Só ignoramos se o assunto for APENAS spam (sem conteúdo real).
SKIP_SUBJECTS_EXACT = ["spam", "[spam]"]

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro",10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

HEADERS = ["UID", "Message-ID", "Assunto", "Remetente", "Recebido", "Status", "Atendente", "Respondido Em"]

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

SYSTEM_SENDER_TOKENS = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "daemon",
    "network management system",
]

_sheet_id_cache = {}

# ── Helpers ───────────────────────────────────────────────────────────
def decode_str(s):
    parts = decode_header(s or "")
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="replace")
        else:
            result += part
    return result

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

def load_last_uid():
    try:
        return int(open(UID_FILE).read().strip())
    except Exception:
        return 0

def save_last_uid(uid):
    with open(UID_FILE, 'w') as f:
        f.write(str(uid))

NORMALIZADO_MARKERS = [
    "normalizado", "restabelecido", "voltou ao normal",
    "resolvido", "encerrar ticket", "encerrar nosso ticket"
]

def get_body_text(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return ""

def get_body_html(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return ""

def parse_date(date_hdr):
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_hdr)
        dt = dt.astimezone(zoneinfo.ZoneInfo("America/Sao_Paulo"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")

def extract_attendant(html):
    full = html or ""
    match = re.search(r'color:\s*#FF9900[^>]*>([^<]{3,80})<', full, re.IGNORECASE)
    if match:
        name = re.sub(r'\s+', ' ', match.group(1)).strip()
        name = re.sub(r'<[^>]+>', '', name).strip()
        if len(name) > 2 and not name.startswith('<'):
            return name
    match2 = re.search(r'assinatura_([a-z_]+)\.html', full, re.IGNORECASE)
    if match2:
        return match2.group(1).replace('_', ' ').title()
    low = full.lower()
    for name in KNOWN_ATTENDANTS:
        if name.lower() in low:
            return name
    return "Desconhecido"

def get_current_sheet_name():
    now = datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo"))
    return f"Emails_{MESES_PT[now.month]}_{now.year}"

def ensure_sheet_exists(service, sheet_name):
    if sheet_name in _sheet_id_cache:
        return _sheet_id_cache[sheet_name]
    spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = {s['properties']['title']: s['properties']['sheetId'] for s in spreadsheet['sheets']}
    if sheet_name not in existing:
        result = service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
        ).execute()
        new_sheet_id = result['replies'][0]['addSheet']['properties']['sheetId']
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{sheet_name}'!A1:H1",
            valueInputOption='RAW',
            body={'values': [HEADERS]}
        ).execute()
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': [{'repeatCell': {
                'range': {'sheetId': new_sheet_id, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
                'fields': 'userEnteredFormat.textFormat'
            }}]}
        ).execute()
        print(f"[NOVA ABA] Criada: {sheet_name}")
        _sheet_id_cache[sheet_name] = new_sheet_id
        return new_sheet_id
    _sheet_id_cache[sheet_name] = existing[sheet_name]
    return existing[sheet_name]

def color_row(service, sheet_id, row_num, r, g, b):
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={'requests': [{'repeatCell': {
            'range': {
                'sheetId': sheet_id,
                'startRowIndex': row_num - 1,
                'endRowIndex': row_num,
                'startColumnIndex': 0,
                'endColumnIndex': 8
            },
            'cell': {'userEnteredFormat': {'backgroundColor': {'red': r, 'green': g, 'blue': b}}},
            'fields': 'userEnteredFormat.backgroundColor'
        }}]}
    ).execute()

def sheet_append(service, sheet_name, sheet_id, row):
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_name}'!A:H",
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body={'values': [row]}
    ).execute()
    updated_range = result['updates']['updatedRange']
    row_num = int(re.search(r'\d+', updated_range.split('!')[1]).group())
    if row[5].strip().lower() == 'spam':
        color_row(service, sheet_id, row_num, r=1.0, g=1.0, b=0.6)
    else:
        color_row(service, sheet_id, row_num, r=1.0, g=0.8, b=0.8)

def sheet_find_and_update(service, sheet_name, sheet_id, message_id, attendant, replied_at, only_if_pending=False, status_label="Respondido"):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_name}'!A:H"
    ).execute()
    rows = result.get('values', [])
    for i, row in enumerate(rows):
        if len(row) > 1 and row[1] == message_id:
            current_status = row[5].strip().lower() if len(row) > 5 else ""
            if only_if_pending and current_status != "pendente":
                return False
            row_num = i + 1
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'{sheet_name}'!F{row_num}:H{row_num}",
                valueInputOption='RAW',
                body={'values': [[status_label, attendant, replied_at]]}
            ).execute()
            if status_label.strip().lower() == "respondido":
                color_row(service, sheet_id, row_num, r=0.8, g=1.0, b=0.8)
            else:
                color_row(service, sheet_id, row_num, r=1.0, g=0.95, b=0.7)
            return True
    return False

def get_sender_display(msg, from_hdr):
    reply_to = decode_str(msg.get("Reply-To", ""))
    if "contatosite@com4.com.br" in from_hdr.lower() and reply_to and "com4.com.br" not in reply_to.lower():
        return f"Via site: {reply_to}"
    return from_hdr

def is_system_sender(sender_display, from_email):
    sender_lower = (sender_display or "").lower()
    email_lower = (from_email or "").lower()
    combined = sender_lower + " " + email_lower
    for token in SYSTEM_SENDER_TOKENS:
        if token in combined:
            return True
    return False

# ── Main ──────────────────────────────────────────────────────────────
def main():
    import socket
    socket.setdefaulttimeout(30)

    service = get_sheets_service()
    sheet_name = get_current_sheet_name()
    sheet_id = ensure_sheet_exists(service, sheet_name)

    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(ACCOUNT, PASSWORD)
    conn.select("INBOX")

    last_uid = load_last_uid()
    s, data = conn.uid("SEARCH", None, f"UID {last_uid + 1}:*")
    if s != "OK" or not data or not data[0]:
        conn.logout()
        return

    uids = data[0].split()
    new_max_uid = last_uid

    for uid in uids:
        uid_int = int(uid)
        if uid_int <= last_uid:
            continue

        try:
            s2, raw = conn.uid("FETCH", uid, "(RFC822)")
            if s2 != "OK" or not raw or not raw[0]:
                continue
            raw_bytes = raw[0][1]
            if not isinstance(raw_bytes, bytes):
                print(f"[AVISO] UID {uid_int}: tipo inesperado ({type(raw_bytes).__name__}), pulando")
                new_max_uid = max(new_max_uid, uid_int)
                continue

            msg = email.message_from_bytes(raw_bytes)

            from_hdr     = decode_str(msg.get("From", ""))
            subject      = decode_str(msg.get("Subject", "(sem assunto)"))
            msg_id       = msg.get("Message-ID", "").strip()
            in_reply     = " ".join(msg.get("In-Reply-To", "").split()).strip()
            date_hdr     = msg.get("Date", "")
            html_body    = get_body_html(msg)
            text_body    = get_body_text(msg)
            subject_lower = subject.lower()

            # Ignora emails de teste (assunto contém palavras de teste)
            # MAS não ignora emails cujo assunto começa com "SPAM:" —
            # isso é prefixo do gateway antispam; o email pode ser legítimo.
            subject_sem_spam_prefix = re.sub(r"^(spam:\s*)+", "", subject_lower, flags=re.IGNORECASE).strip()
            if any(s in subject_sem_spam_prefix for s in SKIP_SUBJECTS):
                print(f"[TESTE IGNORADO] UID {uid_int} | {subject}")
                new_max_uid = max(new_max_uid, uid_int)
                continue
            # Ignora se o assunto for SOMENTE "spam" ou "[spam]" sem conteúdo real
            if subject_lower.strip() in SKIP_SUBJECTS_EXACT:
                print(f"[SPAM IGNORADO] UID {uid_int} | {subject}")
                new_max_uid = max(new_max_uid, uid_int)
                continue

            from_email = email.utils.parseaddr(from_hdr)[1].lower()
            from_lower = from_email or from_hdr.lower()
            is_skip_sender = any(s in from_lower for s in SKIP_SENDERS)
            is_site_contact = (
                from_email == "contatosite@com4.com.br"
                and "com4 site - contato para você" in subject_lower
            )
            is_gateway_spam = (
                "gateway de spam" in from_lower
                or "postmaster@email-gateway2.com4.com.br" in from_lower
            )
            if is_gateway_spam:
                new_max_uid = max(new_max_uid, uid_int)
                continue

            to_hdr = decode_str(msg.get("To", "")).lower()

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

            if (
                from_email.endswith("@com4.com.br")
                and not is_site_contact
                and not in_reply
                and not is_forward_interno
            ):
                print(f"[EMAIL EQUIPE IGNORADO] {subject} | {from_hdr}")
                new_max_uid = max(new_max_uid, uid_int)
                continue

            is_reply_from_attendant = (
                in_reply
                and from_email.endswith("@com4.com.br")
                and not is_skip_sender
                and not is_forward_interno
                and "@com4.com.br" not in in_reply.lower()
            )
            is_client_email = (
                "x-beenthere: atendimento@com4.com.br" in str(msg).lower()
                and not in_reply
                and not is_skip_sender
                and ("atendimento@com4.com.br" not in from_hdr or is_site_contact)
                and not any(s in subject_lower for s in SKIP_SUBJECTS)
                and not is_forward_interno
            )
            is_reply_from_client = (
                in_reply
                and "x-beenthere: atendimento@com4.com.br" in str(msg).lower()
                and not from_email.endswith("@com4.com.br")
                and not is_skip_sender
                and not is_forward_interno
            )

            sender_display = get_sender_display(msg, from_hdr)
            current_sheet_name = get_current_sheet_name()
            current_sheet_id = ensure_sheet_exists(service, current_sheet_name)

            # Prioridade 0: encaminhamento interno
            if is_forward_interno:
                received_at = parse_date(date_hdr)
                attendant = extract_attendant(html_body)
                to_display = decode_str(msg.get("To", "")).strip()
                row = [
                    str(uid_int), msg_id, subject, from_hdr, received_at,
                    f"Encaminhado para {to_display}", attendant, ""
                ]
                try:
                    sheet_append(service, current_sheet_name, current_sheet_id, row)
                    print(f"[ENCAMINHADO] {subject} | para {to_display}")
                    new_max_uid = max(new_max_uid, uid_int)
                except Exception as e:
                    print(f"[ERRO PLANILHA] UID {uid_int} encaminhamento: {e}")
                    # Não avança o UID se falhar — tentará de novo na próxima execução
                continue

            # Prioridade 1: resposta da equipe
            if is_reply_from_attendant:
                attendant = extract_attendant(html_body)
                replied_at = parse_date(date_hdr)
                try:
                    updated = sheet_find_and_update(service, current_sheet_name, current_sheet_id, in_reply, attendant, replied_at)
                    if not updated:
                        print(f"[AVISO] Nao encontrou o email original para In-Reply-To: {in_reply}")
                    new_max_uid = max(new_max_uid, uid_int)
                except Exception as e:
                    print(f"[ERRO PLANILHA] UID {uid_int} resposta equipe: {e}")
                continue

            # Prioridade 2: resposta do cliente
            # Prioridade 2: resposta do cliente
            if is_reply_from_client and not any(s in subject_lower for s in SKIP_SUBJECTS):
                received_at = parse_date(date_hdr)
                matched_attendant = None
                for name in KNOWN_ATTENDANTS:
                    if name.lower() in (html_body or "").lower():
                        matched_attendant = name
                        break
                if not matched_attendant and is_system_sender(sender_display, from_email):
                    matched_attendant = "nao identificado"
                attendant_text = matched_attendant or "nao identificado"

                # Cliente avisando que o problema se resolveu por conta propria
                # (ex: circuito normalizado), sem necessidade de acao da equipe.
                corpo_lower = (text_body or "").lower() + " " + (html_body or "").lower()
                if any(marker in corpo_lower for marker in NORMALIZADO_MARKERS):
                    status_text = "Normalizado - sem ação necessária"
                else:
                    status_text = "Aguardando retorno do atendente"
                try:
                    updated = sheet_find_and_update(
                        service, current_sheet_name, current_sheet_id,
                        in_reply, attendant_text, received_at,
                        only_if_pending=True, status_label=status_text
                    )
                    if not updated:
                        print(f"[AVISO - CLIENTE] Nao encontrou o email original para In-Reply-To: {in_reply}")
                        row = [
                            str(uid_int), msg_id, subject, sender_display, received_at,
                            status_text, attendant_text, received_at
                        ]
                        sheet_append(service, current_sheet_name, current_sheet_id, row)
                    else:
                        print(f"[CLIENTE RESPONDEU] {subject} | {sender_display}")
                    new_max_uid = max(new_max_uid, uid_int)
                except Exception as e:
                    print(f"[ERRO PLANILHA] UID {uid_int} resposta cliente: {e}")
                continue

            elif is_client_email:
                received_at = parse_date(date_hdr)
                row = [
                    str(uid_int), msg_id, subject, sender_display, received_at,
                    "Pendente", "", ""
                ]
                try:
                    sheet_append(service, current_sheet_name, current_sheet_id, row)
                    print(f"[NOVO] {subject} | {sender_display}")
                    new_max_uid = max(new_max_uid, uid_int)
                except Exception as e:
                    print(f"[ERRO PLANILHA] UID {uid_int} novo cliente: {e}")
                    # Não avança o UID se falhar — tentará de novo na próxima execução

            elif is_skip_sender:
                # Spam confirmado: pode avançar o UID pois não precisa inserir na planilha
                print(f"[IGNORADO - SKIP_SENDER] {subject} | {sender_display}")
                new_max_uid = max(new_max_uid, uid_int)

        except Exception as e:
            print(f"[ERRO] UID {uid_int}: {e}")
            new_max_uid = max(new_max_uid, uid_int)
            continue

    save_last_uid(new_max_uid)
    conn.logout()
    print("Concluido.")

if __name__ == "__main__":
    main()
