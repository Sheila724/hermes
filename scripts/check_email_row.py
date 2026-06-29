import os, json, re
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

MESES_PT = {1:'Janeiro',2:'Fevereiro',3:'Marco',4:'Abril',5:'Maio',6:'Junho',7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
SPREADSHEET_ID = os.environ.get('SHEETS_ID', '')
TOKEN_FILE=os.path.expanduser('~/.hermes/google-token.json')

with open(TOKEN_FILE) as f:
    td = json.load(f)
creds = Credentials(
    token=td['token'], refresh_token=td['refresh_token'],
    token_uri=td['token_uri'], client_id=td['client_id'], client_secret=td['client_secret'], scopes=td['scopes']
)
if creds.expired:
    creds.refresh(Request())
    td['token'] = creds.token
    with open(TOKEN_FILE, 'w') as f:
        json.dump(td, f)

service = build('sheets', 'v4', credentials=creds)
now = datetime.now()
name = f"Emails_{MESES_PT[now.month]}_{now.year}"

wa = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{name}'!A:H").execute().get('values', [])
for i, row in enumerate(wa[1:], start=2):
    row += [''] * 8
    subject = row[2] or ''
    attendant = row[6] or ''
    if 'Atendimento' in subject or 'Atendente' in attendant:
        print(i, row[:8])
