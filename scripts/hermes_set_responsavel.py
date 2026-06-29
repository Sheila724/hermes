#!/usr/bin/env python3
"""
hermes_set_responsavel.py — Gestão do responsável semanal de emails

USO MANUAL (a qualquer momento):
    python hermes_set_responsavel.py "Alice Costa"

ROTAÇÃO AUTOMÁTICA (toda segunda-feira via cron):
    Adicione ao crontab:
        0 8 * * 1 /usr/bin/python3 ~/.hermes/scripts/hermes_set_responsavel.py --rodar-rotacao

    A ordem de rotação é definida em ORDEM_ROTACAO abaixo.
    O script lembra quem foi o último e avança para o próximo.

DEFINIR SEM NOTIFICAR O GRUPO:
    python hermes_set_responsavel.py --sem-notificacao "Alice Costa"
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

RESPONSAVEL_FILE = os.path.expanduser("~/.hermes/state/responsavel_semana.json")
WHATSAPP_BRIDGE_PORT = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "3000"))
WHATSAPP_GROUP_JID   = os.environ.get("WHATSAPP_GROUP_JID", "")
os.makedirs(os.path.dirname(RESPONSAVEL_FILE), exist_ok=True)

# ── Edite esta lista para definir a ordem de rotação ──────────────────
# O script avança para o próximo a cada segunda-feira.
ORDEM_ROTACAO = [
    "Alice Costa",
    "Bruno Lima",
    "Carlos Mendes",
    "Diana Souza",
    "Eduardo Faria",
    # Adicione ou remova nomes conforme a equipe mudar
]
# ──────────────────────────────────────────────────────────────────────


def load_state():
    try:
        with open(RESPONSAVEL_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(data):
    with open(RESPONSAVEL_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def send_whatsapp(message):
    url = f"http://127.0.0.1:{WHATSAPP_BRIDGE_PORT}/send"
    payload = json.dumps({"chatId": WHATSAPP_GROUP_JID, "message": message}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        if not body.get("success"):
            raise RuntimeError(f"Bridge respondeu sem sucesso: {body}")


def set_responsavel(nome, notificar=True):
    """Define o responsável da semana e opcionalmente avisa o grupo."""
    state = load_state()
    anterior = state.get("responsavel", "")
    state["responsavel"] = nome
    state["definido_em"] = datetime.now(BRASILIA_TZ).isoformat()
    save_state(state)

    print(f"[OK] Responsável da semana: {nome}")
    if anterior and anterior != nome:
        print(f"     (anterior: {anterior})")

    if notificar:
        agora = datetime.now(BRASILIA_TZ).strftime("%d/%m/%Y")
        mensagem = (
            f"📋 Responsável pelos emails desta semana:\n"
            f"*{nome}*\n\n"
            f"_(definido em {agora})_"
        )
        try:
            send_whatsapp(mensagem)
            print("[OK] Grupo notificado via WhatsApp.")
        except Exception as e:
            print(f"[AVISO] Não foi possível notificar o grupo: {e}")


def rodar_rotacao():
    """Avança para o próximo da lista e define como responsável."""
    if not ORDEM_ROTACAO:
        print("[ERRO] ORDEM_ROTACAO está vazia.")
        sys.exit(1)

    state = load_state()
    atual = state.get("responsavel", "")

    try:
        idx_atual = ORDEM_ROTACAO.index(atual)
        proximo_idx = (idx_atual + 1) % len(ORDEM_ROTACAO)
    except ValueError:
        proximo_idx = 0  # nome atual não está na lista → começa do zero

    set_responsavel(ORDEM_ROTACAO[proximo_idx], notificar=False)


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    if args[0] == "--rodar-rotacao":
        rodar_rotacao()
        return

    if args[0] == "--sem-notificacao" and len(args) > 1:
        nome = " ".join(args[1:]).strip()
        set_responsavel(nome, notificar=False)
        return

    nome = " ".join(args).strip()
    if not nome:
        print('[ERRO] Informe o nome. Ex: python hermes_set_responsavel.py "Alice Costa"')
        sys.exit(1)
    set_responsavel(nome, notificar=False)


if __name__ == "__main__":
    main()
