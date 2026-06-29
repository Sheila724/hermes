#!/usr/bin/env python3
import json, os, sys

RESPONSAVEL_FILE = os.path.expanduser("~/.hermes/state/responsavel_semana.json")

def main():
    if len(sys.argv) < 2:
        print("Uso: set_responsavel_semana.py <nome_do_responsavel>")
        raise SystemExit(1)
    nome = " ".join(sys.argv[1:]).strip()
    if not nome:
        print("Nome vazio.")
        raise SystemExit(1)
    with open(RESPONSAVEL_FILE, "w") as f:
        json.dump({"responsavel": nome}, f, ensure_ascii=False, indent=2)
    print(f"Responsável da semana atualizado para: {nome}")

if __name__ == "__main__":
    main()
