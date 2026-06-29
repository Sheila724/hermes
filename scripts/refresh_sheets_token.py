#!/usr/bin/env python3
"""Renova o token do Google Sheets quando o refresh_token expira."""

import json, os, sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.readonly",
]
TOKEN_FILE=os.path.expanduser("~/.hermes/google-token.json")

with open(TOKEN_FILE) as f:
    td = json.load(f)

client_config = {
    "installed": {
        "client_id": td["client_id"],
        "client_secret": td["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": td["token_uri"],
        "redirect_uris": ["http://localhost"],
    }
}

creds = Credentials(
    token=td["token"],
    refresh_token=td["refresh_token"],
    token_uri=td["token_uri"],
    client_id=td["client_id"],
    client_secret=td["client_secret"],
    scopes=td["scopes"],
)

needs_auth = False
if creds.expired and creds.refresh_token:
    try:
        creds.refresh(Request())
        print("Token renovado com sucesso.")
    except Exception as e:
        print(f"Refresh falhou: {e}")
        needs_auth = True
elif not creds.valid:
    needs_auth = True

if needs_auth:
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    try:
        creds = flow.run_local_server(open_browser=True, port=0)
        print("Autenticacao concluida.")
    except Exception as e:
        print(f"Erro ao abrir navegador: {e}")
        sys.exit(1)

td["token"] = creds.token
if creds.refresh_token:
    td["refresh_token"] = creds.refresh_token
td["token_uri"] = creds.token_uri
td["client_id"] = creds.client_id
td["client_secret"] = creds.client_secret
td["scopes"] = creds.scopes

with open(TOKEN_FILE, "w") as f:
    json.dump(td, f)
print("Token salvo.")
