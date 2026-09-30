# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import itertools
import random
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

KOREN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOREN / "backend"))

from app.data.komponenty import (  # noqa: E402
    SABLONY,
    SablonaKomponenty,
    preloz_hodnotu,
)

VYCHOZI_SEED = 20260817

PODIL_DUPLICIT = 0.20

STAVY = ("ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "PENDING", "OBSOLETE")


@dataclass
class Polozka:
    itemnum: str
    description: str
    long_description: str
    itemtype: str
    commodity_group: str
    order_unit: str
    issue_unit: str
    status: str
    rotating: int
    manufacturer: str
    model_num: str
    vendor: str
    external_ref_id: str
    iso_class: str
    lang_code: str
    change_date: str
    change_by: str
    skupina_id: int = field(default=0)
    je_duplicita: int = field(default=0)
    typ_varianty: str = field(default="originál")
    kod_typu: str = field(default="")
    signatura: str = field(default="")

QWERTZ_SOUSEDE: dict[str, str] = {
    "a": "sq", "b": "vn", "c": "xv", "d": "sf", "e": "wr", "f": "dg", "g": "fh",
    "h": "gj", "i": "uo", "j": "hk", "k": "jl", "l": "k", "m": "n", "n": "bm",
    "o": "ip", "p": "o", "q": "wa", "r": "et", "s": "ad", "t": "rz", "u": "zi",
    "v": "cb", "w": "qe", "x": "yc", "y": "x", "z": "tu",
}


def _bez_diakritiky(text: str) -> str:
    rozlozeny = unicodedata.normalize("NFKD", text)
    return "".join(z for z in rozlozeny if not unicodedata.combining(z))


def varianta_preklep(text: str, rng: random.Random) -> str:
    slova = text.split()
    indexy = [i for i, s in enumerate(slova) if len(s) >= 5 and s.isalpha()]
    if not indexy:
        return text
    idx = rng.choice(indexy)
    slovo = slova[idx]
    pozice = rng.randrange(1, len(slovo) - 1)
    zpusob = rng.choice(("prohozeni", "vynechani", "zdvojeni", "soused"))

    if zpusob == "prohozeni":
        znaky = list(slovo)
        znaky[pozice], znaky[pozice - 1] = znaky[pozice - 1], znaky[pozice]
        slovo = "".join(znaky)
    elif zpusob == "vynechani":
        slovo = slovo[:pozice] + slovo[pozice + 1:]
    elif zpusob == "zdvojeni":
        slovo = slovo[:pozice] + slovo[pozice] + slovo[pozice:]
    else:
        znak = slovo[pozice].lower()
        if znak in QWERTZ_SOUSEDE:
            slovo = slovo[:pozice] + rng.choice(QWERTZ_SOUSEDE[znak]) + slovo[pozice + 1:]

    slova[idx] = slovo
    return " ".join(slova)


def varianta_zkratka(text: str, rng: random.Random) -> str:
    slova = text.split()
    kandidati = [i for i, s in enumerate(slova) if s.isalpha() and len(s) >= 6]
    if not kandidati:
        return text
    rng.shuffle(kandidati)
    for index in kandidati[:2]:
        delka = rng.choice((4, 5))
        slova[index] = slova[index][:delka] + "."
    return " ".join(slova)


def varianta_slovosled(text: str, rng: random.Random) -> str:
    slova = text.split()
    if len(slova) < 2:
        return text
    if rng.random() < 0.5 and len(slova) >= 2:
        slova[0], slova[1] = slova[1], slova[0]
    else:
        slova.append(slova.pop(0))
    return " ".join(slova)


def varianta_bez_diakritiky(text: str, rng: random.Random) -> str:
    bez = _bez_diakritiky(text)
    return bez.upper() if rng.random() < 0.6 else bez


def varianta_interpunkce(text: str, rng: random.Random) -> str:
    oddelovac = rng.choice((", ", " - ", "/"))
    slova = text.split()
    if len(slova) < 3:
        return text
    zlom = rng.randrange(1, len(slova) - 1)
    return " ".join(slova[:zlom]) + oddelovac + " ".join(slova[zlom:])

_VZOR_CISLO_S_JEDNOTKOU = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(mm|kW|kw|bar|A|V|W|K|m3/h|ot/min|rpm|µm|m)\b"
)

ALTERNATIVNI_ZAPISY: dict[str, tuple[str, ...]] = {
    "mm": ("MM", "milimetru", "mm."),
    "kW": ("KW", "kw", "kilowatt"),
    "bar": ("BAR", "barů", "Bar"),
    "ot/min": ("RPM", "rpm", "otáček/min"),
    "rpm": ("RPM", "ot/min", "1/min"),
    "µm": ("um", "mikronu", "mikrometru"),
    "A": ("Amp", "ampér"),
    "V": ("Volt", "VDC"),
    "m3/h": ("m³/h", "M3/H", "m3.h-1"),
}


def varianta_jednotky(text: str, rng: random.Random) -> str:
    shody = list(_VZOR_CISLO_S_JEDNOTKOU.finditer(text))
    if not shody:
        return text
    shoda = rng.choice(shody)
    cislo, jednotka = shoda.group(1), shoda.group(2)

    moznosti: list[str] = []
    if shoda.group(0) == f"{cislo} {jednotka}":
        moznosti.append(f"{cislo}{jednotka}")
    else:
        moznosti.append(f"{cislo} {jednotka}")
    for alternativa in ALTERNATIVNI_ZAPISY.get(jednotka, ()):
        moznosti.append(f"{cislo} {alternativa}")
    if "." in cislo:
        moznosti.append(f"{cislo.replace('.', ',')} {jednotka}")

    moznosti = [m for m in moznosti if m != shoda.group(0)]
    if not moznosti:
        return text
    nahrada = rng.choice(moznosti)
    return text[:shoda.start()] + nahrada + text[shoda.end():]


def varianta_zkraceny(text: str, rng: random.Random) -> str:
    slova = text.split()
    if len(slova) <= 3:
        return text
    obsahuje_cislici = any(any(z.isdigit() for z in s) for s in slova)
    for pocet in (2, 1):
        if len(slova) - pocet < 3:
            continue
        zkraceno = slova[:-pocet]
        if obsahuje_cislici and not any(any(z.isdigit() for z in s) for s in zkraceno):
            continue
        return " ".join(zkraceno)
    return text


TRANSFORMACE = {
    "překlep": varianta_preklep,
    "zkratka": varianta_zkratka,
    "slovosled": varianta_slovosled,
    "bez diakritiky": varianta_bez_diakritiky,
    "interpunkce": varianta_interpunkce,
    "jednotky": varianta_jednotky,
    "zkrácený popis": varianta_zkraceny,
}

VAHY_VARIANT: dict[str, float] = {
    "překlad": 0.30,
    "zkratka": 0.14,
    "slovosled": 0.12,
    "bez diakritiky": 0.10,
    "interpunkce": 0.10,
    "překlep": 0.08,
    "jednotky": 0.06,
    "zkrácený popis": 0.06,
    "kombinovaná": 0.04,
}

def vyjmenuj_platne_kombinace(sablona: SablonaKomponenty) -> list[dict[str, Any]]:
    nazvy = list(sablona.osy.keys())
    platne: list[dict[str, Any]] = []
    for hodnoty in itertools.product(*sablona.osy.values()):
        parametry = dict(zip(nazvy, hodnoty))
        if sablona.je_platna_kombinace(parametry):
            platne.append(parametry)
    return platne


def sestav_popis(sablona: SablonaKomponenty, parametry: dict[str, Any], jazyk: str) -> str:
    if jazyk == "en":
        hodnoty: dict[str, Any] = dict(parametry)
        for klic, hodnota in parametry.items():
            hodnoty[f"{klic}_en"] = preloz_hodnotu(hodnota)
        return sablona.sablona_en.format(**hodnoty)
    return sablona.sablona_cs.format(**parametry)


def signatura_dilu(sablona: SablonaKomponenty, parametry: dict[str, Any]) -> str:
    casti = [f"{klic}={parametry[klic]}" for klic in sorted(parametry)]
    return f"{sablona.kod}|" + "|".join(casti)


def _cislo_modelu(sablona: SablonaKomponenty, parametry: dict[str, Any], rng: random.Random) -> str:
    casti = [str(parametry[k]) for k in sorted(parametry)][:3]
    zaklad = "-".join(str(c).replace(" ", "").replace(".", "")[:6] for c in casti)
    return f"{sablona.kod[:4]}-{zaklad}".upper()


def vytvor_zaznam(
    sablona: SablonaKomponenty,
    parametry: dict[str, Any],
    itemnum: str,
    skupina_id: int,
    jazyk: str,
    typ_varianty: str,
    popis: str,
    rng: random.Random,
    je_duplicita: bool,
) -> Polozka:
    vyrobce = rng.choice(sablona.vyrobci)
    datum = date(2023, 1, 1) + timedelta(days=rng.randrange(0, 1000))
    return Polozka(
        itemnum=itemnum,
        description=popis[:100],
        long_description=(
            f"{popis}. Výrobce: {vyrobce}. "
            f"Zařazení dle ISO 14224: {sablona.trida_iso}."
            if jazyk == "cs"
            else f"{popis}. Manufacturer: {vyrobce}. "
                 f"ISO 14224 class: {sablona.trida_iso}."
        )[:500],
        itemtype="ITEM",
        commodity_group=sablona.komoditni_skupina,
        order_unit=sablona.objednaci_jednotka,
        issue_unit=sablona.objednaci_jednotka,
        status=rng.choice(STAVY),
        rotating=1 if sablona.komoditni_skupina in {"MOTORS", "PUMPS"} and rng.random() < 0.3 else 0,
        manufacturer=vyrobce,
        model_num=_cislo_modelu(sablona, parametry, rng),
        vendor=rng.choice(("ALFA-TECH", "BRNO-MRO", "INDUSTRIA", "TECHNOSERVIS", "MAXIPARTS")),
        external_ref_id=f"{vyrobce[:3].upper()}{rng.randrange(100000, 999999)}",
        iso_class=sablona.trida_iso,
        lang_code=jazyk.upper(),
        change_date=datum.isoformat(),
        change_by=rng.choice(("MCUPAK", "JNOVAK", "PSVOBODA", "ADVORAK", "SYSTEM")),
        skupina_id=skupina_id,
        je_duplicita=1 if je_duplicita else 0,
        typ_varianty=typ_varianty,
        kod_typu=sablona.kod,
        signatura=signatura_dilu(sablona, parametry),
    )


def _vytvor_variantu(
    sablona: SablonaKomponenty,
    parametry: dict[str, Any],
    original: Polozka,
    typ: str,
    typy: list[str],
    vahy: list[float],
    rng: random.Random,
) -> tuple[str, str, str]:
    puvodni_popis = original.description

    def _sestav(zvoleny_typ: str) -> tuple[str, str]:
        if zvoleny_typ == "překlad":
            jazyk = "en" if original.lang_code == "CS" else "cs"
            return sestav_popis(sablona, parametry, jazyk), jazyk
        jazyk = original.lang_code.lower()
        popis = sestav_popis(sablona, parametry, jazyk)
        if zvoleny_typ == "kombinovaná":
            for nazev in rng.sample(list(TRANSFORMACE), k=2):
                popis = TRANSFORMACE[nazev](popis, rng)
        else:
            popis = TRANSFORMACE[zvoleny_typ](popis, rng)
        return popis, jazyk

    poradi_pokusu = [typ] + rng.sample(typy, k=len(typy))
    for zvoleny_typ in poradi_pokusu:
        popis, jazyk = _sestav(zvoleny_typ)
        if popis.strip() and popis != puvodni_popis:
            return popis, zvoleny_typ, jazyk

    return puvodni_popis, "exaktní kopie", original.lang_code.lower()


def generuj_katalog(pocet_zaznamu: int, seed: int) -> list[Polozka]:
    rng = random.Random(seed)

    zasoba: list[tuple[SablonaKomponenty, dict[str, Any]]] = []
    for sablona in SABLONY:
        for parametry in vyjmenuj_platne_kombinace(sablona):
            zasoba.append((sablona, parametry))
    rng.shuffle(zasoba)

    pocet_duplicit = int(pocet_zaznamu * PODIL_DUPLICIT)
    pocet_unikatu = pocet_zaznamu - pocet_duplicit

    if pocet_unikatu > len(zasoba):
        raise SystemExit(
            f"Zásoba obsahuje pouze {len(zasoba)} odlišitelných dílů, "
            f"požadováno {pocet_unikatu} unikátních záznamů. "
            f"Snižte počet záznamů nebo rozšiřte šablony komponent."
        )

    vybrane = zasoba[:pocet_unikatu]

    katalog: list[Polozka] = []
    poradi = itertools.count(100001)
    for skupina_id, (sablona, parametry) in enumerate(vybrane, start=1):
        jazyk = "cs" if rng.random() < 0.65 else "en"
        popis = sestav_popis(sablona, parametry, jazyk)
        katalog.append(vytvor_zaznam(
            sablona, parametry, str(next(poradi)), skupina_id, jazyk,
            "originál", popis, rng, je_duplicita=False,
        ))

    typy = list(VAHY_VARIANT.keys())
    vahy = [VAHY_VARIANT[t] for t in typy]
    indexy_pro_duplikaci = rng.sample(range(len(vybrane)), k=min(pocet_duplicit, len(vybrane)))

    for i in range(pocet_duplicit):
        index_zdroje = indexy_pro_duplikaci[i % len(indexy_pro_duplikaci)]
        sablona, parametry = vybrane[index_zdroje]
        original = katalog[index_zdroje]
        typ = rng.choices(typy, weights=vahy, k=1)[0]

        popis, typ, jazyk_varianty = _vytvor_variantu(
            sablona, parametry, original, typ, typy, vahy, rng,
        )

        katalog.append(vytvor_zaznam(
            sablona, parametry, str(next(poradi)), original.skupina_id,
            jazyk_varianty, typ, popis, rng, je_duplicita=True,
        ))

    rng.shuffle(katalog)
    return katalog

SLOUPCE_KATALOGU = [
    "ITEMNUM", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "ITEMTYPE",
    "COMMODITYGROUP", "ORDERUNIT", "ISSUEUNIT", "STATUS", "ROTATING",
    "MANUFACTURER", "MODELNUM", "VENDOR", "EXTERNALREFID", "ISOCLASS",
    "LANGCODE", "CHANGEDATE", "CHANGEBY",
]

SLOUPCE_GROUND_TRUTH = [
    "ITEMNUM", "SKUPINA_ID", "JE_DUPLICITA", "TYP_VARIANTY", "KOD_TYPU", "SIGNATURA",
]


def zapis_katalog(katalog: list[Polozka], cesta: Path) -> None:
    cesta.parent.mkdir(parents=True, exist_ok=True)
    with cesta.open("w", encoding="utf-8", newline="") as soubor:
        zapisovac = csv.writer(soubor, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        zapisovac.writerow(SLOUPCE_KATALOGU)
        for p in katalog:
            zapisovac.writerow([
                p.itemnum, p.description, p.long_description, p.itemtype,
                p.commodity_group, p.order_unit, p.issue_unit, p.status, p.rotating,
                p.manufacturer, p.model_num, p.vendor, p.external_ref_id,
                p.iso_class, p.lang_code, p.change_date, p.change_by,
            ])


def zapis_ground_truth(katalog: list[Polozka], cesta: Path) -> None:
    cesta.parent.mkdir(parents=True, exist_ok=True)
    with cesta.open("w", encoding="utf-8", newline="") as soubor:
        zapisovac = csv.writer(soubor, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        zapisovac.writerow(SLOUPCE_GROUND_TRUTH)
        for p in katalog:
            zapisovac.writerow([
                p.itemnum, p.skupina_id, p.je_duplicita, p.typ_varianty,
                p.kod_typu, p.signatura,
            ])


def vypis_statistiku(katalog: list[Polozka]) -> None:
    skupiny: dict[int, int] = {}
    for p in katalog:
        skupiny[p.skupina_id] = skupiny.get(p.skupina_id, 0) + 1
    duplicitni_skupiny = {k: v for k, v in skupiny.items() if v > 1}
    varianty: dict[str, int] = {}
    jazyky: dict[str, int] = {}
    for p in katalog:
        varianty[p.typ_varianty] = varianty.get(p.typ_varianty, 0) + 1
        jazyky[p.lang_code] = jazyky.get(p.lang_code, 0) + 1

    print(f"  Záznamů celkem            : {len(katalog)}")
    print(f"  Skupin (unikátních dílů)  : {len(skupiny)}")
    print(f"  Skupin s duplicitou       : {len(duplicitni_skupiny)}")
    print(f"  Duplicitních záznamů      : {sum(1 for p in katalog if p.je_duplicita)}")
    pocet_paru = sum(v * (v - 1) // 2 for v in skupiny.values())
    print(f"  Skutečně duplicitních dvojic: {pocet_paru}")
    print("\n  Rozdělení podle typu varianty:")
    for typ, pocet in sorted(varianty.items(), key=lambda x: -x[1]):
        print(f"    {typ:<22} {pocet:>6}")
    print("\n  Rozdělení podle jazyka:")
    for jazyk, pocet in sorted(jazyky.items()):
        print(f"    {jazyk:<22} {pocet:>6}")


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
