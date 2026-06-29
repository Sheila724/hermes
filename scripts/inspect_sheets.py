import os, json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = os.path.expanduser('~/.hermes/google-token.json')
SPREADSHEET_ID = os.environ.get('SHEETS_ID', '')
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

service = build('sheets', 'v4', credentials=creds)
meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
sheets = [[s['properties']['title']] for s in meta.get('sheets', [])]
print('ABAS:')
for row in sheets[-10:]:
    print(row[0])

current = sorted([s[0] for s in sheets if s[0].startswith('Emails_')])[-1]
print('ABA_ATUAL', current)
res = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{current}'!A2:H12").execute()
rows = res.get('values', [])
print('PRIMEIRAS_LINHAS')
for i, row in enumerate(rows, start=2):
    print(i, row)
