# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

KOREN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOREN / "backend"))

from app.data.glosar_zdroj import TerminGlosare, vsechny_terminy  # noqa: E402
from app.data.iso14224 import (  # noqa: E402
    DRUHY_PORUCH,
    TRIDY_ZARIZENI,
    UDRZBOVE_CINNOSTI,
)
from app.data.komponenty import SABLONY  # noqa: E402

SLOUPCE = ["ID", "TERMIN_EN", "TERMIN_CS", "KATEGORIE", "DEFINICE", "NESPRAVNE", "ZDROJ"]


def terminy_z_iso() -> list[TerminGlosare]:
    polozky: list[TerminGlosare] = []

    for trida in TRIDY_ZARIZENI:
        polozky.append(TerminGlosare(
            termin_en=trida.nazev_en,
            termin_cs=trida.nazev_cs,
            kategorie="ISO 14224 - třída zařízení",
            definice=f"Třída zařízení {trida.kod}, kategorie {trida.kategorie}.",
            zdroj="ISO 14224",
        ))

    for kod, nazev_en, nazev_cs in DRUHY_PORUCH:
        polozky.append(TerminGlosare(
            termin_en=nazev_en,
            termin_cs=nazev_cs,
            kategorie="ISO 14224 - druh poruchy",
            definice=f"Druh poruchy s kódem {kod} podle ISO 14224.",
            zdroj="ISO 14224",
        ))

    for kod, nazev_en, nazev_cs in UDRZBOVE_CINNOSTI:
        polozky.append(TerminGlosare(
            termin_en=nazev_en,
            termin_cs=nazev_cs,
            kategorie="ISO 14224 - údržbová činnost",
            definice=f"Kategorie údržbové činnosti s kódem {kod} podle ISO 14224.",
            zdroj="ISO 14224",
        ))

    polozky.append(TerminGlosare(
        termin_en="failure mode",
        termin_cs="způsob poruchy",
        kategorie="ISO 14224 - druh poruchy",
        definice="Způsob, jakým se porucha projevuje; terminologie dle ISO 14224.",
        zdroj="ISO 14224",
    ))
    polozky.append(TerminGlosare(
        termin_en="failure mechanism",
        termin_cs="mechanismus poruchy",
        kategorie="ISO 14224 - druh poruchy",
        definice="Fyzikální proces vedoucí k poruše; terminologie dle ISO 14224.",
        zdroj="ISO 14224",
    ))
    polozky.append(TerminGlosare(
        termin_en="equipment class",
        termin_cs="třída zařízení",
        kategorie="ISO 14224 - třída zařízení",
        definice="Zařazení zařízení do taxonomie podle ISO 14224.",
        zdroj="ISO 14224",
    ))
    return polozky


def terminy_z_katalogu() -> list[TerminGlosare]:
    return [
        TerminGlosare(
            termin_en=sablona.nazev_en,
            termin_cs=sablona.nazev_cs,
            kategorie="komponenta",
            definice=f"Komoditní skupina {sablona.komoditni_skupina}, "
                     f"třída ISO 14224: {sablona.trida_iso}.",
            zdroj="katalog položek",
        )
        for sablona in SABLONY
    ]


def sestav_glosar() -> list[TerminGlosare]:
    podle_klice: dict[str, TerminGlosare] = {}

    for skupina in (vsechny_terminy(), terminy_z_iso(), terminy_z_katalogu()):
        for termin in skupina:
            klic = termin.termin_en.strip().lower()
            if klic not in podle_klice:
                podle_klice[klic] = termin

    return sorted(podle_klice.values(), key=lambda t: t.termin_en.lower())


def zapis_glosar(polozky: list[TerminGlosare], cesta: Path) -> None:
    cesta.parent.mkdir(parents=True, exist_ok=True)
    with cesta.open("w", encoding="utf-8", newline="") as soubor:
        zapisovac = csv.writer(soubor, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        zapisovac.writerow(SLOUPCE)
        for poradi, t in enumerate(polozky, start=1):
            zapisovac.writerow([
                f"G{poradi:04d}", t.termin_en, t.termin_cs, t.kategorie,
                t.definice, t.nespravne, t.zdroj,
            ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generátor firemního glosáře.")
    parser.add_argument("--vystup", type=Path, default=KOREN / "data" / "vstup" / "glosar.csv")
    argumenty = parser.parse_args()

    print("=" * 70)
    print("SESTAVENÍ FIREMNÍHO GLOSÁŘE")
    print("=" * 70)

    polozky = sestav_glosar()
    zapis_glosar(polozky, argumenty.vystup)

    podle_kategorie: dict[str, int] = {}
    podle_zdroje: dict[str, int] = {}
    for t in polozky:
        podle_kategorie[t.kategorie] = podle_kategorie.get(t.kategorie, 0) + 1
        podle_zdroje[t.zdroj] = podle_zdroje.get(t.zdroj, 0) + 1

    print(f"  Termínů celkem: {len(polozky)}")
    print(f"  S upozorněním na nesprávný překlad: "
          f"{sum(1 for t in polozky if t.nespravne)}")
    print("\n  Podle zdroje:")
    for zdroj, pocet in sorted(podle_zdroje.items(), key=lambda x: -x[1]):
        print(f"    {zdroj:<24} {pocet:>4}")
    print("\n  Podle kategorie:")
    for kategorie, pocet in sorted(podle_kategorie.items(), key=lambda x: -x[1]):
        print(f"    {kategorie:<34} {pocet:>4}")
    print(f"\n  Glosář: {argumenty.vystup}")


if __name__ == "__main__":
    main()
