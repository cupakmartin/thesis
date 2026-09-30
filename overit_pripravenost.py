# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import time
from pathlib import Path

KOREN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOREN / "backend"))

V_PORADKU = "  [ v pořádku ]"
VAROVANI = "  [ upozornění ]"
CHYBA = "  [   CHYBA    ]"

pocet_chyb = 0
pocet_varovani = 0


def vypis(stav: str, nazev: str, podrobnost: str = "") -> None:
    global pocet_chyb, pocet_varovani
    if stav == CHYBA:
        pocet_chyb += 1
    elif stav == VAROVANI:
        pocet_varovani += 1
    print(f"{stav}  {nazev}")
    if podrobnost:
        for radek in podrobnost.splitlines():
            print(f"                 {radek}")


def zkontroluj_prostredi() -> None:
    print("\n── PROSTŘEDÍ " + "─" * 58)

    verze = sys.version_info
    if verze >= (3, 11):
        vypis(V_PORADKU, f"Python {verze.major}.{verze.minor}.{verze.micro}")
    else:
        vypis(CHYBA, f"Python {verze.major}.{verze.minor}",
              "Vyžadována je verze 3.11 nebo novější.")

    chybejici: list[str] = []
    for modul in ("torch", "sentence_transformers", "faiss", "fastapi",
                  "langchain_core", "rapidfuzz", "sacrebleu", "sklearn"):
        try:
            __import__(modul)
        except ImportError:
            chybejici.append(modul)

    if chybejici:
        vypis(CHYBA, "Závislosti",
              f"Chybí: {', '.join(chybejici)}\n"
              f"Spusťte: .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
    else:
        vypis(V_PORADKU, "Všechny závislosti nainstalovány")


def zkontroluj_data() -> None:
    print("\n── DATA " + "─" * 63)

    soubory = {
        "Katalog položek": KOREN / "data" / "vstup" / "katalog.csv",
        "Ground truth": KOREN / "data" / "vstup" / "ground_truth.csv",
        "Glosář": KOREN / "data" / "vstup" / "glosar.csv",
    }
    for nazev, cesta in soubory.items():
        if cesta.exists():
            radku = sum(1 for _ in cesta.open(encoding="utf-8")) - 1
            vypis(V_PORADKU, f"{nazev} — {radku} záznamů")
        else:
            skript = ("generuj_dataset.py" if "atalog" in nazev or "round" in nazev
                      else "generuj_glosar.py")
            vypis(CHYBA, nazev,
                  f"Soubor chybí. Spusťte: "
                  f".venv\\Scripts\\python.exe backend\\skripty\\{skript}")

    cache = list((KOREN / "data" / "cache").glob("embeddingy_*.npz"))
    if cache:
        velikost = sum(c.stat().st_size for c in cache) / 1_048_576
        vypis(V_PORADKU, f"Cache vektorů — {velikost:.0f} MB",
              "První spuštění bude okamžité.")
    else:
        vypis(VAROVANI, "Cache vektorů chybí",
              "První deduplikace potrvá přibližně minutu.\n"
              "Doporučuji ji před předvedením spustit nanečisto.")


def zkontroluj_modely() -> None:
    print("\n── MODELY " + "─" * 61)

    adresar = KOREN / "modely"
    if adresar.exists() and any(adresar.rglob("*.safetensors")):
        vypis(V_PORADKU, "Embedding model stažen lokálně")
    else:
        vypis(VAROVANI, "Embedding model není v adresáři projektu",
              "Stáhne se při prvním použití — vyžaduje připojení k internetu.")

    try:
        from app.config import nastaveni
        from app.jadro.llm import OllamaPoskytovatel

        konfigurace = nastaveni()
        poskytovatel = OllamaPoskytovatel(konfigurace)
        if not poskytovatel.je_dostupny():
            vypis(CHYBA, "Služba Ollama neběží",
                  "Spusťte ji; bez ní nebude funkční překlad.")
            return

        modely = poskytovatel.seznam_modelu()
        vypis(V_PORADKU, f"Ollama běží — {len(modely)} modelů",
              ", ".join(modely) if modely else "")

        if konfigurace.model_llm not in modely:
            vypis(CHYBA, f"Výchozí model {konfigurace.model_llm} není nainstalován",
                  f"Spusťte: ollama pull {konfigurace.model_llm}")
        else:
            vypis(V_PORADKU, f"Výchozí model {konfigurace.model_llm} připraven")
    except Exception as chyba:
        vypis(CHYBA, "Kontrola jazykového modelu selhala", str(chyba))


def zkontroluj_rozhrani() -> None:
    print("\n── UŽIVATELSKÉ ROZHRANÍ " + "─" * 47)

    dist = KOREN / "frontend" / "dist"
    if (dist / "index.html").exists():
        soubory = list(dist.rglob("*"))
        velikost = sum(s.stat().st_size for s in soubory if s.is_file()) / 1_048_576
        vypis(V_PORADKU, f"Rozhraní sestaveno — {velikost:.1f} MB",
              "Ke spuštění není potřeba Node.js.")
    else:
        vypis(CHYBA, "Rozhraní není sestaveno",
              "Spusťte ve složce frontend: npm install && npm run build")


def zkontroluj_funkcnost() -> None:
    print("\n── FUNKČNÍ ZKOUŠKA " + "─" * 52)

    try:
        from app.jadro.atributy import porovnej_atributy, vytez_atributy
        from app.jadro.typy import urci_typ

        shodne = porovnej_atributy(
            vytez_atributy("Ložisko kuličkové 6204 2RS"),
            vytez_atributy("Ball bearing 6204 2RS"),
        )
        odlisne = porovnej_atributy(
            vytez_atributy("Ložisko kuličkové 6204 2RS"),
            vytez_atributy("Ložisko kuličkové 6205 2RS"),
        )
        if not shodne.rozpor and odlisne.rozpor:
            vypis(V_PORADKU, "Atributové porovnání",
                  "6204 CS/EN rozpoznáno jako shodné, 6204 vs 6205 jako odlišné.")
        else:
            vypis(CHYBA, "Atributové porovnání vrací nesprávný výsledek")

        zpetny = urci_typ("Check valve DN125 PN16")
        kulovy = urci_typ("Ball valve DN125 PN16")
        cesky = urci_typ("Ventil zpětný DN125 PN16")
        if (zpetny and kulovy and cesky
                and zpetny.identifikator != kulovy.identifikator
                and zpetny.identifikator == cesky.identifikator):
            vypis(V_PORADKU, "Určení druhu komponenty",
                  "Zpětný a kulový ventil odlišeny, CS/EN spárovány.")
        else:
            vypis(CHYBA, "Určení druhu komponenty selhalo")
    except Exception as chyba:
        vypis(CHYBA, "Kontrola deduplikace selhala", str(chyba))

    try:
        from app.jadro.llm import OllamaPoskytovatel
        from app.jadro.rag import PozadavekPrekladu, PrekladacRAG
        from app.jadro.validace import zvaliduj_preklad

        if not OllamaPoskytovatel().je_dostupny():
            vypis(VAROVANI, "Zkouška překladu přeskočena", "Ollama neběží.")
            return

        cas = time.time()
        prekladac = PrekladacRAG()
        vysledek = prekladac.prelozi(PozadavekPrekladu(
            text="Replace the impeller and seal on the centrifugal pump.",
            zdrojovy_jazyk="en", cilovy_jazyk="cs", pouzit_glosar=True,
        ))
        validace = zvaliduj_preklad(
            vysledek.zdrojovy_text, vysledek.preklad, vysledek.nalezene_terminy,
        )
        doba = time.time() - cas

        if validace.mira_dodrzeni_glosare >= 0.6:
            vypis(V_PORADKU,
                  f"Překlad s glosářem — dodrženo "
                  f"{validace.mira_dodrzeni_glosare:.0%} termínů, {doba:.1f} s",
                  f"„{vysledek.preklad}“")
        else:
            vypis(VAROVANI,
                  f"Překlad dodržel pouze {validace.mira_dodrzeni_glosare:.0%} termínů",
                  f"„{vysledek.preklad}“")
    except Exception as chyba:
        vypis(CHYBA, "Zkouška překladu selhala", str(chyba))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


    print("=" * 72)
    print("  OVĚŘENÍ PŘIPRAVENOSTI APLIKACE")
    print("=" * 72)

    zkontroluj_prostredi()
    zkontroluj_data()
    zkontroluj_modely()
    zkontroluj_rozhrani()
    zkontroluj_funkcnost()

    print("\n" + "=" * 72)
    if pocet_chyb:
        print(f"  ZJIŠTĚNO {pocet_chyb} CHYB a {pocet_varovani} upozornění.")
        print("  Aplikace není plně připravena — odstraňte chyby uvedené výše.")
    elif pocet_varovani:
        print(f"  Vše podstatné je v pořádku, {pocet_varovani} upozornění.")
        print("  Aplikaci lze spustit příkazem:  .venv\\Scripts\\python.exe spustit.py")
    else:
        print("  VŠE JE PŘIPRAVENO.")
        print("  Aplikaci spustíte příkazem:  .venv\\Scripts\\python.exe spustit.py")
    print("=" * 72)

    sys.exit(1 if pocet_chyb else 0)


if __name__ == "__main__":
    main()
