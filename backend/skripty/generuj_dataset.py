# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys
from pathlib import Path

KOREN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOREN / "backend"))

from app.data.generator_katalogu import (
    VYCHOZI_SEED,
    generuj_katalog,
    vypis_statistiku,
    zapis_ground_truth,
    zapis_katalog,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generátor testovacího katalogu kmenových dat MRO.",
    )
    parser.add_argument("--pocet", type=int, default=5000,
                        help="celkový počet záznamů katalogu (výchozí 5000)")
    parser.add_argument("--seed", type=int, default=VYCHOZI_SEED,
                        help="inicializace generátoru náhodných čísel")
    parser.add_argument("--vystup", type=Path, default=KOREN / "data" / "vstup",
                        help="adresář pro uložení výstupních souborů")
    argumenty = parser.parse_args()

    print("=" * 70)
    print("GENEROVÁNÍ TESTOVACÍHO KATALOGU KMENOVÝCH DAT")
    print("=" * 70)

    katalog = generuj_katalog(argumenty.pocet, argumenty.seed)

    cesta_katalogu = argumenty.vystup / "katalog.csv"
    cesta_gt = argumenty.vystup / "ground_truth.csv"
    zapis_katalog(katalog, cesta_katalogu)
    zapis_ground_truth(katalog, cesta_gt)

    vypis_statistiku(katalog)
    print(f"\n  Katalog      : {cesta_katalogu}")
    print(f"  Ground truth : {cesta_gt}")
    print(f"  Seed         : {argumenty.seed} (dataset je reprodukovatelný)")


if __name__ == "__main__":
    main()
