"""Monta o dict `report` (consumido por render_html_com4.render_html) a partir
das linhas da planilha Google Sheets do mês atual (aba "Emails_<Mês>_<Ano>").

Usa a mesma fonte do extrair.py / com4_sla_alert.py para não depender do
CSV publicado da aba "Consolidado", que está desativada.
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
SPREADSHEET_ID = os.environ.get("SHEETS_ID", "")
TOKEN_FILE = os.path.expanduser("~/.hermes/google-token.json")

MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

COLUNAS = ["UID", "Message-ID", "Assunto", "Remetente", "Recebido", "Status", "Atendente", "Respondido Em"]


def _get_sheet_name():
    now = datetime.now(BRASILIA_TZ)
    return f"Emails_{MESES_PT[now.month]}_{now.year}"


def _get_sheets_service():
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
    return build("sheets", "v4", credentials=creds)


def carregar_linhas():
    service = _get_sheets_service()
    sheet_name = _get_sheet_name()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"'{sheet_name}'!A:H")
        .execute()
    )
    valores = result.get("values", [])[1:]  # pula cabeçalho

    linhas = []
    for r in valores:
        if not any(v.strip() for v in r):
            continue
        linha = {COLUNAS[i]: (r[i].strip() if i < len(r) else "") for i in range(len(COLUNAS))}
        linhas.append(linha)
    return linhas


def parse_recebido(linha):
    """Converte a coluna Recebido (dd/mm/yyyy HH:MM[:SS]) em datetime."""
    valor = (linha.get("Recebido") or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            pass
    return None


def filtrar_periodo(linhas, data_inicio, data_fim):
    """Mantém apenas as linhas cujo Recebido cai dentro de [data_inicio, data_fim]."""
    selecionadas = []
    for linha in linhas:
        recebido = parse_recebido(linha)
        if recebido and data_inicio <= recebido <= data_fim:
            selecionadas.append(linha)
    return selecionadas


def email_considerado(linha):
    """Um e-mail só é considerado se a planilha não marcou a linha como Spam.

    Mesma regra do painel (dashboard/extrair.py linha 86): a linha é Spam se
    Status OU Atendente vierem marcados como "Spam".
    """
    status = (linha.get("Status") or "").strip().lower()
    atendente = (linha.get("Atendente") or "").strip().lower()
    return status != "spam" and atendente != "spam"


def construir_report(linhas, periodo_label, data_inicio, data_fim):
    """Constrói o dict de `report` usado por render_html_com4.render_html,
    usando a nova lógica do painel e respeitando a categoria editável.
    """
    considerados = [linha for linha in linhas if email_considerado(linha)]

    respondidos_linhas = [
        linha for linha in considerados
        if (linha.get("Status") or "").strip().lower().startswith("respondido")
    ]

    aguardando_linhas = [
        linha for linha in considerados
        if (linha.get("Status") or "").strip().lower().replace("_", " ") == "aguardando retorno do atendente"
        or (linha.get("Atendente") or "").strip().lower() == "aguardando retorno do atendente"
    ]

    por_atendente = {}
    for linha in respondidos_linhas:
        atendente = (linha.get("Atendente") or "").strip()
        if not atendente:
            continue
        por_atendente[atendente] = por_atendente.get(atendente, 0) + 1

    total_emails = len(considerados)
    respondidos = len(respondidos_linhas)
    aguardando_atendente = len(aguardando_linhas)
    pendentes = total_emails - respondidos - aguardando_atendente

    return {
        "periodo_label": periodo_label,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "total_emails": total_emails,
        "respondidos": respondidos,
        "pendentes": pendentes,
        "aguardando_atendente": aguardando_atendente,
        "por_atendente": por_atendente,
    }
