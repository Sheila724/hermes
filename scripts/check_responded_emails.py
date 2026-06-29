#!/usr/bin/env python3
import os, json, re
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

TOKEN_FILE = os.path.expanduser("~/.hermes/google-token.json")
SPREADSHEET_ID = os.environ.get("SHEETS_ID", "")
STATE_FILE = os.path.expanduser("~/.hermes/state/wa_responded_notified.json")
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

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

SKIP_SUBJECTS = [
    "teste", "spam", "[spam]", "test", "testing",
    "e-mail teste", "email teste",
]

GENERIC_ATTENDANTS = {"Atendente", "", None}

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

service = build("sheets", "v4", credentials=creds)
now = datetime.now()
sheet_name = f"Emails_{MESES_PT[now.month]}_{now.year}"

emails_res = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID, range=f"'{sheet_name}'!A:H"
).execute()
wa_res = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID, range="WhatsApp Notifications!A:G"
).execute()

emails = emails_res.get("values", [])
wa_rows = wa_res.get("values", [])

wa_map = {row[0]: row[1] for row in wa_rows[1:] if len(row) >= 2}

try:
    with open(STATE_FILE) as f:
        notified = set(json.load(f).get("notified_email_ids", []))
except Exception:
    notified = set()

pending = []
for i, row in enumerate(emails[1:], start=2):
    parts = (row + [""] * 8)[:8]
    msg_id = parts[1]
    subject = parts[2]
    sender = parts[3]
    status = parts[5]
    attendant = parts[6]
    replied_at = parts[7]

    if (
        (
            status.strip().lower() == "respondido"
            or status.strip().lower().startswith("cliente respondeu")
        )
        and msg_id
        and msg_id not in notified
        and not any(tok in (subject or "").lower() for tok in SKIP_SUBJECTS)
        and (attendant or "").strip() not in GENERIC_ATTENDANTS
    ):
        pending.append({
            "row": i,
            "email_msg_id": msg_id,
            "wa_msg_id": wa_map.get(msg_id),
            "replied_at": replied_at,
            "attendant": attendant,
            "subject": subject or "(sem assunto)",
            "sender": sender or "(remetente desconhecido)",
            "message": (
                "Respondido\n"
                f"De: {sender or '(remetente desconhecido)'}\n"
                f"Assunto: {subject or '(sem assunto)'}\n"
                f"Por: _{attendant}_ em {replied_at or '(sem data)'}"
            ),
        })

notified.update({p["email_msg_id"] for p in pending})
with open(STATE_FILE, "w") as f:
    json.dump({"notified_email_ids": list(notified)}, f)

print(json.dumps({"pending": pending}, ensure_ascii=False))
