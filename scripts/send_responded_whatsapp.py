#!/usr/bin/env python3
import json, os, sys, urllib.request

RECIPIENT = os.environ.get("WHATSAPP_RECIPIENT", "")
WHATSAPP_BRIDGE_PORT = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "3000"))

def main():
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_responded_emails.py")
    proc = __import__("subprocess").run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode != 0:
        print(f"[ERRO] check_responded_emails.py falhou: {proc.stderr}")
        return

    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        print(f"[ERRO] JSON inválido: {exc}")
        return

    pending = data.get("pending", [])
    if not pending:
        print("Nenhum email respondido pendente.")
        return

    if len(pending) > 1:
        separator = "\n\n----------------------------------------\n\n"
    else:
        separator = "\n\n"

    messages = []
    for item in pending:
        message = item.get("message")
        if not message:
            continue
        if isinstance(message, list):
            message = "\n".join(message)
        messages.append(str(message).strip())

    text = separator.join(messages)
    payload = json.dumps({"chatId": RECIPIENT, "message": text}).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{WHATSAPP_BRIDGE_PORT}/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("success"):
                print(f"[ENVIADO] {len(messages)} notificacao(oes) para {RECIPIENT}")
            else:
                print(f"[ERRO] Bridge retornou falha: {body}")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar WhatsApp: {e}")

if __name__ == "__main__":
    main()
