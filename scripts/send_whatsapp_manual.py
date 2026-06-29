#!/usr/bin/env python3
"""
Disparo manual de mensagens no grupo de WhatsApp da COM4.
Uso:
  python3 send_whatsapp_manual.py "Mensagem aqui"
"""
import json
import os
import sys
import urllib.request

WHATSAPP_BRIDGE_PORT = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "3000"))
WHATSAPP_GROUP_JID = os.environ.get("WHATSAPP_GROUP_JID", "")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 send_whatsapp_manual.py 'mensagem'")
        sys.exit(1)
    mensagem = " ".join(sys.argv[1:])
    payload = json.dumps({"chatId": WHATSAPP_GROUP_JID, "message": mensagem}).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{WHATSAPP_BRIDGE_PORT}/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        if body.get("success"):
            print("OK")
        else:
            print("FALHA:", body)
            sys.exit(2)


if __name__ == "__main__":
    main()
