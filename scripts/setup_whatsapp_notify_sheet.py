import os, json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = os.path.expanduser("~/.hermes/google-token.json")
SPREADSHEET_ID = os.environ.get("SHEETS_ID", "")

with open(TOKEN_FILE) as f:
    td = json.load(f)
creds = Credentials(token=td['token'], refresh_token=td['refresh_token'], token_uri=td['token_uri'], client_id=td['client_id'], client_secret=td['client_secret'], scopes=td['scopes'])
if creds.expired:
    creds.refresh(Request())
    td['token'] = creds.token
    with open(TOKEN_FILE, 'w') as f:
        json.dump(td, f)

service = build('sheets', 'v4', credentials=creds)
service.spreadsheets().batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={
        "requests": [{"addSheet": {"properties": {"title": "WhatsApp Notifications", "gridProperties": {"rowCount": 10000, "columnCount": 7}}}}]
    }
).execute()
service.spreadsheets().values().update(
    spreadsheetId=SPREADSHEET_ID,
    range="WhatsApp Notifications!A1:G1",
    valueInputOption="RAW",
    body={"values": [["email_message_id", "wa_message_id", "group_id", "notified_at", "responded", "responded_at", "responded_by"]]}
).execute()
print("done")
