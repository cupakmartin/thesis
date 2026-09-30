# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

KOREN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOREN / "backend"))


def zkontroluj_prostredi() -> list[str]:
    problemy: list[str] = []

    if not (KOREN / "data" / "vstup" / "katalog.csv").exists():
        problemy.append(
            "Chybí katalog položek. Spusťte:\n"
            "    .venv\\Scripts\\python.exe backend\\skripty\\generuj_dataset.py"
        )

    if not (KOREN / "data" / "vstup" / "glosar.csv").exists():
        problemy.append(
            "Chybí glosář. Spusťte:\n"
            "    .venv\\Scripts\\python.exe backend\\skripty\\generuj_glosar.py"
        )

    if not (KOREN / "modely").exists():
        problemy.append(
            "Chybí adresář se staženým embedding modelem. "
            "Model se stáhne automaticky při prvním použití, "
            "což vyžaduje připojení k internetu."
        )

    return problemy


def zkontroluj_ollamu(url: str) -> tuple[bool, list[str]]:
    try:
        from ollama import Client

        odpoved = Client(host=url).list()
        modely = [
            str(m.get("model") or m.get("name"))
            for m in odpoved.get("models", [])
            if m.get("model") or m.get("name")
        ]
        return True, sorted(modely)
    except Exception:
        return False, []


def main() -> None:
    parser = argparse.ArgumentParser(description="Spuštění aplikace MRO Master Data AI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bez-prohlizece", action="store_true",
                        help="nespouštět automaticky webový prohlížeč")
    parser.add_argument("--znovu-nacitat", action="store_true",
                        help="automatické načtení změn kódu (pro vývoj)")
    argumenty = parser.parse_args()

    print("=" * 72)
    print("  MRO MASTER DATA AI")
    print("  Sjednocení katalogů a překlad technických textů pomocí AI")
    print("=" * 72)

    problemy = zkontroluj_prostredi()
    if problemy:
        print("\n  UPOZORNĚNÍ:")
        for problem in problemy:
            print(f"    - {problem}")
        print()

    os.environ.setdefault("HF_HOME", str(KOREN / "modely"))

    from app.config import nastaveni

    konfigurace = nastaveni()
    dostupna, modely = zkontroluj_ollamu(konfigurace.ollama_url)

    print(f"\n  Embedding model : {konfigurace.model_embeddingu}")
    print(f"  Jazykový model  : {konfigurace.model_llm}")
    if dostupna:
        print(f"  Ollama          : běží, {len(modely)} modelů "
              f"({', '.join(modely) if modely else 'žádný'})")
        if konfigurace.model_llm not in modely:
            print(f"    POZOR: model {konfigurace.model_llm} není nainstalován. "
                  f"Spusťte: ollama pull {konfigurace.model_llm}")
    else:
        print("  Ollama          : NEBĚŽÍ — překlad nebude funkční.")
        print("                    Spusťte službu Ollama a zkuste znovu.")

    adresa = f"http://{argumenty.host}:{argumenty.port}"
    print(f"\n  Rozhraní        : {adresa}")
    print(f"  Dokumentace API : {adresa}/api/dokumentace")
    print("\n  Ukončení: Ctrl+C")
    print("=" * 72 + "\n")

    if not argumenty.bez_prohlizece:
        def _oteviri_prohlizec() -> None:
            time.sleep(2.0)
            webbrowser.open(adresa)

        threading.Thread(target=_oteviri_prohlizec, daemon=True).start()

    import uvicorn

    uvicorn.run(
        "app.main:aplikace",
        host=argumenty.host,
        port=argumenty.port,
        reload=argumenty.znovu_nacitat,
        log_level="info",
    )


if __name__ == "__main__":
    main()
